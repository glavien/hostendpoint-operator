# Calico HostEndpoint Operator

[![CI Checks](https://github.com/glavien-io/hostendpoint-operator/actions/workflows/ci.yaml/badge.svg)](https://github.com/glavien-io/hostendpoint-operator/actions/workflows/ci.yaml)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/glavien-io/hostendpoint-operator)](https://github.com/glavien-io/hostendpoint-operator/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A simple, lightweight Kubernetes operator that automatically creates and manages [Calico HostEndpoint](https://docs.tigera.io/calico/latest/reference/resources/hostendpoint) resources for every node in your cluster.

This operator is designed to bridge the gap between Kubernetes nodes and Calico's host protection policies, enabling a true "infrastructure as code" approach to securing your cluster's control plane and node-level services.

---

## 🚀 What It Solves

In a Kubernetes cluster using Calico for networking, `NetworkPolicy` resources secure pod-to-pod traffic. However, they do not protect the nodes themselves. To apply network policies directly to your nodes (for example, to restrict access to the Kubernetes API server or SSH port), you need `HostEndpoint` resources.

Manually creating a `HostEndpoint` for every node is tedious, error-prone, and doesn't scale. This operator automates the process entirely.

**Key Features:**
*   **Automatic Discovery:** Continuously watches for new nodes joining the cluster.
*   **HostEndpoint Creation:** Automatically creates a `HostEndpoint` for each discovered node.
*   **State Reconciliation:** Ensures that existing `HostEndpoint` resources are always in sync with the node's current state (IP addresses, labels).
*   **Self-Healing:** If a `HostEndpoint` is accidentally deleted, the operator will recreate it on the next scan.
*   **Lightweight & Secure:** Built in Python with minimal dependencies, runs as a non-root user with a read-only filesystem.

## ✨ Getting Started

### Prerequisites

- A Kubernetes cluster (v1.25+ recommended)
- Calico installed as the CNI and configured to manage network policies
- Helm v3+ installed

### 📦 Installation: The Safe Rollout Strategy

> ⚠️ **IMPORTANT WARNING: AVOIDING LOCKOUT**  
> Enabling HostEndpoints without pre-existing Allow policies can lock you out of your cluster (both SSH and kubectl access). You MUST create failsafe rules and baseline network policies BEFORE installing the operator. Follow these steps in order.

#### Step 1: Configure Failsafe Ports (Your Emergency Hatch)

First, create a FelixConfiguration to ensure you can never be locked out of critical management ports, no matter what policies are applied.

**01-felix-config.yaml**
```yaml
apiVersion: crd.projectcalico.org/v1
kind: FelixConfiguration
metadata:
    name: default # The name must be 'default'
spec:
    # These ports will ALWAYS be open for inbound traffic to the host.
    failsafeInboundHostPorts:
        # Administrative Access (SSH)
        - protocol: tcp
            port: 22
        # Kubernetes API Server  
        - protocol: tcp
            port: 6443
        # RKE2/K3s Registration Port
        - protocol: tcp
            port: 9345
```

Apply this configuration:
```bash
kubectl apply -f 01-felix-config.yaml
```

#### Step 2: Create Baseline Allow Policies

Now, create a GlobalNetworkPolicy that explicitly allows access for your administrative tasks and for intra-cluster communication.

**02-allow-admin-and-cluster.yaml**
```yaml
apiVersion: crd.projectcalico.org/v1
kind: GlobalNetworkPolicy
metadata:
    name: allow-admin-and-cluster
spec:
    # Apply with a high priority (low order number)
    order: 10
    # Apply this policy to all host endpoints
    selector: "has(kubernetes.io/hostname)"
    # Allow all egress traffic so nodes can talk to each other and the internet
    # Define specific rules for incoming traffic
    ingress:
        # Rule 1: Allow SSH and Kube API from your trusted IP
        - action: Allow
            protocol: TCP
            source:
                nets:
                    - "YOUR_OFFICE_IP/32" # <-- IMPORTANT: Change this to your static IP!
            destination:
                ports:
                    - 22
                    - 6443
        # Rule 2: Allow all traffic from within the private network (for etcd, etc.)
        - action: Allow
            source:
                nets:
                    - "10.0.0.0/16" # <-- IMPORTANT: Change this to your cluster's private network CIDR
```

> **IMPORTANT:** Before applying, change `YOUR_OFFICE_IP/32` to your real IP address and `10.0.0.0/16` to your private network range.

Apply the policy:
```bash
kubectl apply -f 02-allow-admin-and-cluster.yaml
```

#### Step 3: Now, Install the Operator

With the safety net in place, you can now safely install the operator.

Add the Glavien Software Helm repository:
```bash
helm repo add glavien https://glavien.github.io/helm-charts
helm repo update
```

Install the chart:
```bash
helm install hostendpoint-operator glavien/hostendpoint-operator \
    --namespace kube-system
```

The operator will now start creating HostEndpoints, and they will immediately be protected by the policies you created, ensuring you retain access.

## ⚙️ Configuration

The operator is configured via environment variables, which can be set in the `values.yaml` file of the Helm chart.

| Helm Value (config.*) | Environment Variable | Description | Default |
|----------------------|---------------------|-------------|---------|
| `logLevel` | `LOG_LEVEL` | The logging level. Can be `DEBUG`, `INFO`, `WARNING`, `ERROR`. | `INFO` |
| `scanIntervalSeconds` | `SCAN_INTERVAL_SECONDS` | How often (in seconds) the operator checks for node changes. | `60` |
| `operatorId` | `OPERATOR_ID` | A unique ID used for labels on managed resources. | `glavien.io/hostendpoint-operator` |

**Example of customizing the installation with Helm:**
```bash
helm install hostendpoint-operator glavien/hostendpoint-operator \
  --namespace kube-system \
  --set config.logLevel=DEBUG \
  --set config.scanIntervalSeconds=30
```

## 🛡️ Example Use Case: Securing the Kubernetes API

Once the operator has created HostEndpoints for all your nodes, you can apply a `GlobalNetworkPolicy` to restrict access to the control plane.

This example policy allows access to the Kubernetes API (port 6443) only from a trusted IP range (e.g., your office network).

**allow-api-access.yaml**
```yaml
apiVersion: crd.projectcalico.org/v1
kind: GlobalNetworkPolicy
metadata:
  name: allow-api-access
spec:
  # Apply this policy with a high priority (low order number)
  order: 10
  # Apply this policy to all host endpoints in the cluster
  selector: "has(kubernetes.io/hostname)"
  # Define rules for incoming traffic
  ingress:
     - action: Allow
        protocol: TCP
        source:
          nets:
             - "YOUR_OFFICE_IP/32" # <-- IMPORTANT: Change this!
        destination:
          ports:
             - 6443
  # Explicitly allow all egress traffic from the hosts
  egress:
     - action: Allow
```

Apply it with `kubectl apply -f allow-api-access.yaml`. Now, only connections from your trusted IP will be able to reach the API server.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
