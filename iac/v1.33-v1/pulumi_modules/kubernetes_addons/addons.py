"""
Kubernetes Add-ons (Cilium CNI and CoreDNS)
Equivalent to terraform/modules/kubernetes-addons
"""

import pulumi
import pulumi_kubernetes as k8s
from typing import Any


def create_kubernetes_addons(
    cluster_name: str,
    cluster_endpoint: pulumi.Output,
    cluster_ca_certificate: pulumi.Output,
    pod_cidr_range: str,
    enable_cilium: bool,
    enable_coredns: bool,
    cluster: Any,
    aws_auth_configmap: Any,
    region: str,
) -> dict:
    """
    Install Kubernetes add-ons via Helm
    
    Args:
        cluster_name: Name of the EKS cluster
        cluster_endpoint: Cluster endpoint URL
        cluster_ca_certificate: Base64-encoded cluster CA certificate
        pod_cidr_range: CIDR range for pods
        enable_cilium: Whether to install Cilium CNI
        enable_coredns: Whether to install CoreDNS
        cluster: EKS cluster resource (for dependency)
        aws_auth_configmap: aws-auth ConfigMap (for dependency)
        region: AWS region where the cluster lives
        
    Returns:
        Dictionary containing addon resources
    """
    
    # Create Kubernetes provider
    k8s_provider = k8s.Provider(
        f"{cluster_name}-addons-k8s-provider",
        kubeconfig=pulumi.Output.all(
            cluster_endpoint,
            cluster_ca_certificate,
        ).apply(lambda args: f"""apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: {args[1]}
    server: {args[0]}
  name: {cluster_name}
contexts:
- context:
    cluster: {cluster_name}
    user: {cluster_name}
  name: {cluster_name}
current-context: {cluster_name}
kind: Config
preferences: {{}}
users:
- name: {cluster_name}
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws
      args:
        - eks
        - get-token
        - --cluster-name
        - {cluster_name}
        - --region
        - {region}
"""),
        opts=pulumi.ResourceOptions(depends_on=[cluster, aws_auth_configmap]),
    )
    
    result = {}
    
    # Install Cilium CNI
    if enable_cilium:
        cluster_host = cluster_endpoint.apply(lambda ep: ep.replace("https://", ""))
        
        cilium_values = pulumi.Output.all(cluster_host, pod_cidr_range, cluster_name).apply(
            lambda args: {
                "kubeProxyReplacement": True,
                "autoDirectNodeRoutes": True,
                "ipv4NativeRoutingCIDR": args[1],
                "k8sServiceHost": args[0],
                "k8sServicePort": 443,
                "routingMode": "native",
                "extraArgs": ["--devices=ens+"],
                "enableIPv4Masquerade": True,
                "enableIPv6Masquerade": True,
                "loadBalancer": {
                    "algorithm": "maglev",
                    "mode": "dsr",
                },
                "ipam": {
                    "mode": "eni",
                    "eni": {
                        "enabled": True,
                        "subnetTags": {
                            f"kubernetes.io/cluster/{args[2]}": "owned"
                        },
                        "securityGroupTags": {
                            f"kubernetes.io/cluster/{args[2]}": "owned"
                        },
                    },
                },
                "eni": {
                    "enabled": True,
                    "subnetTags": {
                        f"kubernetes.io/cluster/{args[2]}": "owned"
                    },
                    "securityGroupTags": {
                        f"kubernetes.io/cluster/{args[2]}": "owned"
                    },
                },
                "devices": ["eth0"],
                "bpf": {
                    "masquerade": True,
                    "datapathMode": "netkit",
                },
                "nodePort": {
                    "enabled": True,
                },
                "cluster": {
                    "name": args[2],
                },
                "operator": {
                    "replicas": 1,
                    "prometheus": {
                        "enabled": True,
                    },
                    "image": {
                        "repository": "quay.io/cilium/operator",
                        "tag": "v1.16.4",
                    },
                    "tolerations": [
                        {
                            "key": "node-type",
                            "operator": "Equal",
                            "value": "core",
                            "effect": "NoSchedule",
                        }
                    ],
                },
                "hubble": {
                    "enabled": True,
                    "relay": {
                        "enabled": True,
                        "tolerations": [
                            {
                                "key": "node-type",
                                "operator": "Equal",
                                "value": "core",
                                "effect": "NoSchedule",
                            }
                        ],
                    },
                    "ui": {
                        "enabled": True,
                        "tolerations": [
                            {
                                "key": "node-type",
                                "operator": "Equal",
                                "value": "core",
                                "effect": "NoSchedule",
                            }
                        ],
                    },
                },
                "prometheus": {
                    "enabled": True,
                },
                "image": {
                    "repository": "quay.io/cilium/cilium",
                    "tag": "v1.16.4",
                },
            }
        )
        
        cilium_release = k8s.helm.v3.Release(
            "cilium",
            name="cilium",
            chart="cilium",
            repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                repo="https://helm.cilium.io/",
            ),
            version="1.18.3",
            namespace="kube-system",
            values=cilium_values,
            skip_await=False,
            opts=pulumi.ResourceOptions(
                provider=k8s_provider,
                depends_on=[cluster, aws_auth_configmap],
                ignore_changes=["values"],
            ),
        )
        
        result["cilium_release"] = cilium_release
    
    # Install CoreDNS
    if enable_coredns:
        coredns_values = {
            "image": {
                "repository": "coredns/coredns",
                "tag": "1.11.1",
            },
            "replicaCount": 2,
            "service": {
                "type": "ClusterIP",
                "clusterIP": "172.20.0.10",
            },
            "resources": {
                "limits": {
                    "memory": "170Mi",
                    "cpu": "100m",
                },
                "requests": {
                    "memory": "70Mi",
                    "cpu": "100m",
                },
            },
            "podAnnotations": {
                "prometheus.io/port": "9153",
                "prometheus.io/scrape": "true",
            },
            "tolerations": [
                {
                    "key": "node-type",
                    "operator": "Equal",
                    "value": "core",
                    "effect": "NoSchedule",
                }
            ],
            "servers": [
                {
                    "zones": [
                        {
                            "zone": ".",
                        }
                    ],
                    "port": 53,
                    "plugins": [
                        {"name": "errors"},
                        {
                            "name": "health",
                            "configBlock": "lameduck 5s",
                        },
                        {"name": "ready"},
                        {
                            "name": "kubernetes",
                            "parameters": "cluster.local in-addr.arpa ip6.arpa",
                            "configBlock": "pods insecure\nfallthrough in-addr.arpa ip6.arpa\nttl 30",
                        },
                        {
                            "name": "prometheus",
                            "parameters": "0.0.0.0:9153",
                        },
                        {
                            "name": "forward",
                            "parameters": ". /etc/resolv.conf",
                            "configBlock": "max_concurrent 1000",
                        },
                        {
                            "name": "cache",
                            "parameters": 30,
                        },
                        {"name": "loop"},
                        {"name": "reload"},
                        {"name": "loadbalance"},
                    ],
                }
            ],
        }
        
        deps = [cluster, aws_auth_configmap]
        if "cilium_release" in result:
            deps.append(result["cilium_release"])
        
        coredns_release = k8s.helm.v3.Release(
            "coredns",
            name="coredns",
            chart="coredns",
            repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                repo="https://coredns.github.io/helm/",
            ),
            version="1.25.0",
            namespace="kube-system",
            values=coredns_values,
            skip_await=False,
            opts=pulumi.ResourceOptions(
                provider=k8s_provider,
                depends_on=deps,
            ),
        )
        
        result["coredns_release"] = coredns_release
    
    return result

