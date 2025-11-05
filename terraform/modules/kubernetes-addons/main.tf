terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
}

# Data sources for cluster authentication
data "aws_eks_cluster_auth" "main" {
  name = var.cluster_name
}

# Cilium CNI
resource "helm_release" "cilium" {
  count = var.enable_cilium ? 1 : 0

  name       = "cilium"
  repository = "https://helm.cilium.io/"
  chart      = "cilium"
  version    = "1.18.3"
  namespace  = "kube-system"
  
  create_namespace = true

  values = [
    templatefile(
      "${path.module}/values/cilium-values.yaml.tmpl",
      {
        cluster_name = var.cluster_name,
        cluster_host = replace(var.cluster_endpoint, "https://", "")
        pod_cidr_range = var.pod_cidr_range
      }
    )
  ]

  lifecycle {
    ignore_changes = all
  }

  depends_on = [
    var.cluster_endpoint
  ]
}

# CoreDNS
resource "helm_release" "coredns" {
  count = var.enable_coredns ? 1 : 0

  name       = "coredns"
  repository = "https://coredns.github.io/helm/"
  chart      = "coredns"
  version    = "1.25.0"
  namespace  = "kube-system"
  
  create_namespace = true

  values = [
    yamlencode({
      image = {
        repository = "coredns/coredns"
        tag        = "1.11.1"
      }
      replicaCount = 2
      service = {
        type      = "ClusterIP"
        clusterIP = "172.20.0.10"
      }
      resources = {
        limits = {
          memory = "170Mi"
          cpu    = "100m"
        }
        requests = {
          memory = "70Mi"
          cpu    = "100m"
        }
      }
      podAnnotations = {
        "prometheus.io/port"   = "9153"
        "prometheus.io/scrape" = "true"
      }
      tolerations = [
        {
          key      = "node-type"
          operator = "Equal"
          value    = "core"
          effect   = "NoSchedule"
        }
      ]
      servers = [
        {
          zones = [
            {
              zone = "."
            }
          ]
          port = 53
          plugins = [
            {
              name = "errors"
            },
            {
              name        = "health"
              configBlock = "lameduck 5s"
            },
            {
              name = "ready"
            },
            {
              name       = "kubernetes"
              parameters = "cluster.local in-addr.arpa ip6.arpa"
              configBlock = "pods insecure\nfallthrough in-addr.arpa ip6.arpa\nttl 30"
            },
            {
              name       = "prometheus"
              parameters = "0.0.0.0:9153"
            },
            {
              name       = "forward"
              parameters = ". /etc/resolv.conf"
              configBlock = "max_concurrent 1000"
            },
            {
              name       = "cache"
              parameters = 30
            },
            {
              name = "loop"
            },
            {
              name = "reload"
            },
            {
              name = "loadbalance"
            }
          ]
        }
      ]
    })
  ]

  depends_on = [
    var.cluster_endpoint,
    helm_release.cilium
  ]
}

