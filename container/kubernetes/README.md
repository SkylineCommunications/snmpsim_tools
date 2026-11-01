# Deploy on Kubernetes

These steps run an image built with [build.sh](../build.sh) on a Kubernetes cluster without a container registry. The image is exported to a file, copied to the worker nodes, and imported into their container runtime. SNMP managers outside the cluster (e.g., DataMiner) poll the simulated agent on a port of the nodes (NodePort).

[snmpsim.yaml](snmpsim.yaml) is the template of the Kubernetes manifest: a Deployment that runs the image, and a Service that publishes it on a NodePort.

>[!TIP]
> With a container registry, you do not need to export and import the image. Push the image to the registry with `podman push`, use its name in the registry in the manifest, and remove `imagePullPolicy: Never`. Use a private registry, as simulation files can contain data of real devices.

## Overview

The steps run on different machines:

1. [Export the image](#1-export-the-image): on the machine where the image was built
2. [Import the image on the worker nodes](#2-import-the-image-on-the-worker-nodes): on each worker node
3. [Create the manifest](#3-create-the-manifest): on the machine where the image was built
4. [Deploy the simulation](#4-deploy-the-simulation): on the control node, or any other machine with `kubectl` access to the cluster
5. [Test the simulation](#5-test-the-simulation): on a machine outside the cluster, e.g., the SNMP manager

The examples use the image `localhost/my_device:1.0.0` and the NodePort 30161. On the machine where the image was built, open a shell in the `container` folder and set these variables, so you can copy the commands as they are:

```bash
name=my_device    # image name
version=1.0.0     # image version
nodePort=30161    # port on the nodes: free, and in the NodePort range of the cluster (default 30000-32767)
```

These variables are not set on the nodes, so the commands that run there use the example names.

## 1. Export the image

Run the commands without `sudo`. Podman stores the images of a regular user in the home folder of this user, so `sudo podman` does not find them.

1. Export the image to a file:

   ```bash
   podman save --format docker-archive -o "kubernetes/${name}_${version}.tar" "localhost/$name:$version"
   ```

   The file will be about 160 MB. Both containerd and CRI-O can import this format.

   Always export the image by name and version, never by image ID. A file exported from an image ID does not contain the image name, so Kubernetes does not find the image after the import (`ErrImageNeverPull`).

2. Check the image name in the file:

   ```bash
   tar -xOf "kubernetes/${name}_${version}.tar" manifest.json | grep -o '"RepoTags":\[[^]]*\]'
   ```

   The output will be `"RepoTags":["localhost/my_device:1.0.0"]`. This name must be identical to the `image` in the manifest.

## 2. Import the image on the worker nodes

1. On the control node, check the container runtime of the nodes:

   ```bash
   kubectl get nodes -o wide
   ```

   The CONTAINER-RUNTIME column will show the runtime of each node, e.g., `containerd://2.3.4`.

2. Copy the file to each worker node:

   ```bash
   scp "kubernetes/${name}_${version}.tar" <user>@<worker-node>:/tmp/
   ```

3. On each worker node, import the image with the command of its container runtime:

   - containerd: `sudo ctr -n k8s.io images import /tmp/my_device_1.0.0.tar`
   - k3s: `sudo k3s ctr images import /tmp/my_device_1.0.0.tar`
   - RKE2: `sudo /var/lib/rancher/rke2/bin/ctr --address /run/k3s/containerd/containerd.sock -n k8s.io images import /tmp/my_device_1.0.0.tar`
   - CRI-O: `sudo podman load -i /tmp/my_device_1.0.0.tar`

   With containerd, the namespace `k8s.io` is required, as Kubernetes does not use the images of other namespaces.

4. On each worker node, check that the image is available:

   ```bash
   sudo crictl images | grep my_device
   ```

   The output will show `localhost/my_device` with the tag `1.0.0`.

5. On each worker node, remove the file:

   ```bash
   rm /tmp/my_device_1.0.0.tar
   ```

Keep the following in mind:

- The nodes must have the same CPU architecture as the machine where the image was built (e.g., x86_64)
- Control-plane nodes only need the image when they run regular pods. The control-plane nodes of kubeadm clusters do not, while k3s and RKE2 servers do by default. Nodes with the taint `node-role.kubernetes.io/control-plane:NoSchedule` do not run regular pods. To show the taints of the nodes, run `kubectl describe nodes | grep -E '^(Name|Taints):'`
- To import the image on one node only, uncomment the `nodeSelector` in the manifest and fill in the name of this node

## 3. Create the manifest

1. Create the manifest of the simulation from the template:

   ```bash
   sed -e "s/my-device/${name//_/-}/g" -e "s/my_device/$name/g" \
       -e "s/1\.0\.0/$version/g" -e "s/30161/$nodePort/g" \
       kubernetes/snmpsim.yaml > "kubernetes/$name.yaml"
   ```

   The manifest will be created as `kubernetes/my_device.yaml`. It is excluded from the repository.

2. Copy the manifest to the control node.

The command replaces the example values of the template:

- `my_device`: the image name
- `my-device`: the name of the Kubernetes objects (`snmpsim-my-device`). `${name//_/-}` derives it from the image name, because Kubernetes names cannot contain `_`
- `1.0.0`: the image version
- `30161`: the NodePort

Each simulation needs its own manifest, with its own names and NodePort. Applying a manifest with the names of another simulation replaces that simulation.

## 4. Deploy the simulation

1. On the control node, apply the manifest:

   ```bash
   kubectl apply -n <namespace> -f my_device.yaml
   ```

2. Check the pod and the service:

   ```bash
   kubectl get pods,services -n <namespace> -l app.kubernetes.io/instance=my-device
   ```

   After a few seconds, the pod will have the status `Running`, and the service will show the port `161:30161/UDP`.

3. Check the logs:

   ```bash
   kubectl logs -n <namespace> deploy/snmpsim-my-device
   ```

   The logs will contain the line `Listening at UDP/IPv4 endpoint 0.0.0.0:1161`.

## 5. Test the simulation

On a machine outside the cluster, poll the simulated agent on the IP address of any node and the NodePort:

```bash
snmpget -v2c -c public <node-ip>:30161 1.3.6.1.2.1.1.1.0
```

In an SNMP manager such as DataMiner, use the IP address of a node, port 30161, and the SNMP community `public`. When there is no answer, check that the firewall of the nodes allows UDP traffic to the NodePort.

## Update a simulation

1. Build the image with a new version:

   ```bash
   ./build.sh data/my_device.snmprec my_device:1.0.1
   ```

2. Export the image and import it on the worker nodes, as described in steps 1 and 2.
3. Create the manifest again as described in step 3, or change the version in the `image` line of the manifest.
4. Apply the manifest as described in step 4.

   Kubernetes will start a pod with the new version, and then stop the pod with the old version.

Always use a new version. When the version does not change, the manifest does not change either, so `kubectl apply` does not replace the running pod.

## Add another simulation

Repeat the steps with another image name and another NodePort (e.g., 30162). Each simulation runs in its own pod.

## Troubleshooting

- **The pod has the status `ErrImageNeverPull`**: the node that runs the pod does not have the image. Import the image on this node (with containerd, in the namespace `k8s.io`), and check the image name in the exported file (step 1). The pod starts automatically after the import. Alternatively, use the `nodeSelector` of the manifest to run the pod on a node that has the image
- **The image disappears from a node**: when the disk of a node is almost full, Kubernetes removes the images that are not in use. Import the image again
- **There is no SNMP answer**: check the logs of the pod (step 4), the NodePort of the service, and the firewall of the nodes (UDP)

## Security

- The pod runs as a non-root user, with a read-only root file system, without Linux capabilities, and with the default seccomp profile. Only `/tmp` is writable, as snmpsim creates its index there. The manifest meets the `restricted` [Pod Security Standard](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- The image and the exported file contain the simulation file. Simulation files of real devices can contain sensitive data (e.g., IP addresses, serial numbers, or configuration), so keep them internal

## Use a load balancer

When the cluster has a load balancer (e.g., MetalLB, kube-vip, or the load balancer of a cloud provider), change `type: NodePort` to `type: LoadBalancer` in the manifest. The simulation will get its own external IP address with the standard SNMP port 161.
