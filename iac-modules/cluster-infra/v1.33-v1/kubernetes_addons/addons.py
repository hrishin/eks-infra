"""
Kubernetes Add-ons (Cilium CNI and CoreDNS)
Equivalent to terraform/modules/kubernetes-addons
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional

import pulumi
import pulumi_kubernetes as k8s
import yaml


_DEFAULT_CILIUM_VALUES_BASE: Dict[str, Any] = {
    "autoDirectNodeRoutes": True,
    "bpf": {
        "datapathMode": "netkit",
        "masquerade": True,
    },
    "cluster": {
        "name": "",
    },
    "devices": ["eth0"],
    "enableIPv4Masquerade": True,
    "enableIPv6Masquerade": True,
    "extraArgs": ["--devices=ens+"],
    "hubble": {
        "enabled": True,
        "relay": {
            "enabled": True,
            "tolerations": [
                {
                    "effect": "NoSchedule",
                    "key": "node-type",
                    "operator": "Equal",
                    "value": "core",
                }
            ],
        },
        "ui": {
            "enabled": True,
            "tolerations": [
                {
                    "effect": "NoSchedule",
                    "key": "node-type",
                    "operator": "Equal",
                    "value": "core",
                }
            ],
        },
    },
    "image": {
        "repository": "quay.io/cilium/cilium",
        "tag": "v1.16.4",
    },
    "ipam": {
        "eni": {
            "enabled": True,
            "securityGroupTags": {},
            "subnetTags": {},
        },
        "mode": "eni",
    },
    "k8sServiceHost": "",
    "k8sServicePort": 443,
    "kubeProxyReplacement": True,
    "loadBalancer": {
        "algorithm": "maglev",
        "mode": "dsr",
    },
    "nodePort": {
        "enabled": True,
    },
    "operator": {
        "image": {
            "repository": "quay.io/cilium/operator",
            "tag": "v1.16.4",
        },
        "prometheus": {
            "enabled": True,
        },
        "replicas": 1,
        "tolerations": [
            {
                "effect": "NoSchedule",
                "key": "node-type",
                "operator": "Equal",
                "value": "core",
            }
        ],
    },
    "prometheus": {
        "enabled": True,
    },
    "routingMode": "native",
}


_DEFAULT_COREDNS_VALUES: Dict[str, Any] = {
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


def _load_yaml_mapping(file_path: str, component_name: str) -> Dict[str, Any]:
    try:
        with open(file_path, "r") as file:
            data = yaml.safe_load(file) or {}
    except FileNotFoundError:
        pulumi.log.warn(f"{component_name} values file {file_path} not found. Falling back to defaults.")
        return {}
    except Exception as exc:  # noqa: BLE001
        pulumi.log.warn(
            f"Failed to load {component_name} values from {file_path}: {exc}. Falling back to defaults."
        )
        return {}

    if not isinstance(data, dict):
        pulumi.log.warn(
            f"{component_name} values file {file_path} must deserialize to a mapping. Falling back to defaults."
        )
        return {}

    return data


def _set_nested_value(target: Dict[str, Any], keys: List[str], value: Any) -> None:
    current: Dict[str, Any] = target
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


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
    cilium_values_path: Optional[str] = None,
    coredns_values_path: Optional[str] = None,
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
        cilium_values_path: Optional path to YAML file with base values for the Cilium Helm release
        coredns_values_path: Optional path to YAML file with base values for the CoreDNS Helm release
        
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

    cilium_base_values: Dict[str, Any] = {}
    if enable_cilium and cilium_values_path:
        cilium_base_values = _load_yaml_mapping(cilium_values_path, "Cilium")
    coredns_base_values: Dict[str, Any] = {}
    if enable_coredns and coredns_values_path:
        coredns_base_values = _load_yaml_mapping(coredns_values_path, "CoreDNS")
    
    # Install Cilium CNI
    if enable_cilium:
        cluster_host = cluster_endpoint.apply(lambda ep: ep.replace("https://", ""))
        
        cilium_values_base = deepcopy(cilium_base_values) if cilium_base_values else {}

        def build_cilium_values(args: List[str]) -> Dict[str, Any]:
            cluster_host_value, pod_cidr_value, cluster_name_value = args

            values = deepcopy(cilium_values_base) if cilium_values_base else deepcopy(_DEFAULT_CILIUM_VALUES_BASE)

            cluster_tag_value = {f"kubernetes.io/cluster/{cluster_name_value}": "owned"}

            _set_nested_value(values, ["ipv4NativeRoutingCIDR"], pod_cidr_value)
            _set_nested_value(values, ["k8sServiceHost"], cluster_host_value)
            _set_nested_value(values, ["cluster", "name"], cluster_name_value)
            _set_nested_value(values, ["ipam", "eni", "subnetTags"], cluster_tag_value)
            _set_nested_value(values, ["ipam", "eni", "securityGroupTags"], cluster_tag_value)
            _set_nested_value(values, ["eni", "subnetTags"], cluster_tag_value)
            _set_nested_value(values, ["eni", "securityGroupTags"], cluster_tag_value)

            return values

        cilium_values = pulumi.Output.all(cluster_host, pod_cidr_range, cluster_name).apply(build_cilium_values)
        
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
                retain_on_delete=True,
            ),
        )
        
        result["cilium_release"] = cilium_release
    
    # Install CoreDNS
    if enable_coredns:
        coredns_values = deepcopy(coredns_base_values) if coredns_base_values else deepcopy(_DEFAULT_COREDNS_VALUES)
        
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
                ignore_changes=["values"],
                retain_on_delete=True,
            ),
        )
        
        result["coredns_release"] = coredns_release
    
    return result

