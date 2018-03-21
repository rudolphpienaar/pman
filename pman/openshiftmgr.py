"""
OpenShift cluster manager module that provides functionality to schedule jobs as well as
manage their state in the cluster.
"""

import yaml
import json
import os
from kubernetes import client as k_client
from openshift import client as o_client
from openshift import config


class OpenShiftManager(object):

    def __init__(self, project=None):
        self.openshift_client = None
        self.kube_client = None
        self.kube_v1_batch_client = None
        self.project = project or os.environ.get('OPENSHIFTMGR_PROJECT') or 'myproject'

        # init the openshift client
        self.init_openshift_client()

    def init_openshift_client(self):
        """
        Method to get a OpenShift client connected to remote or local OpenShift
        """
        kubecfg_path = os.environ.get('KUBECFG_PATH')
        if kubecfg_path is None:
            config.load_kube_config()
        else:
            config.load_kube_config(config_file=kubecfg_path)
        self.openshift_client = o_client.OapiApi()
        self.kube_client = k_client.CoreV1Api()
        self.kube_v1_batch_client = k_client.BatchV1Api()

    # The kubecfg secret being mounted in the third container (publish) is the one that is generated by the service account
    def schedule(self, image, command, name, number_of_workers, 
                 cpu_limit, memory_limit, gpu_limit):
        """
        Schedule a new job and returns the job object.
        """
        d_job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": name
            },
            "spec": {
                "parallelism": number_of_workers,
                "completions": number_of_workers,
                "activeDeadlineSeconds": 3600,
                "template": {
                    "metadata": {
                        "name": name
                    },
                    "spec": {
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "env": [
                                    {
                                        "name": "NUMBER_OF_WORKERS",
                                        "value": number_of_workers
                                    },
                                    {
                                        "name": "CPU_LIMIT",
                                        "value": cpu_limit
                                    },
                                    {
                                        "name": "MEMORY_LIMIT",
                                        "value": memory_limit
                                    }
                                ],
                                "name": name,
                                "image": image,
                                "command": command.split(" "),
                                "resources": {
                                    "limits": {
                                        "memory": memory_limit,
                                        "cpu": cpu_limit
                                    },
                                    "requests": {
                                        "memory": "128Mi",
                                        "cpu": "250m"
                                    }
                                },
                                "volumeMounts": [
                                    {
                                        "mountPath": "/share",
                                        "name": "shared-volume"
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
        if int(gpu_limit) > 0:  # Typecasting before a check
            # The assumption is containers[0] is always image plugin pod as the publish container is appended later.
            # These is specific to 3.9+  Ref: https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/
            d_job['spec']['template']['spec']['containers'][0]['resources']['limits']['nvidia.com/gpu'] = int(gpu_limit)
            # Add node selector for node.
            d_job['spec']['template']['spec']['nodeSelector'] = {'accelerator': 'gpu-node'}


        if os.environ.get('STORAGE_TYPE') == 'swift':
            d_job['spec']['template']['spec']['initContainers'] = [
                {
                    "name": "init-storage",
                    "image": "fnndsc/pman-swift-publisher",
                    "env": [
                        {
                            "name": "SWIFT_KEY",
                            "value": name
                        }
                    ],
                    "command": [
                        "python3",
                        "get_data.py"
                    ],
                    "resources": {
                        "limits": {
                            "memory": "1024Mi",
                            "cpu": "2000m"
                        },
                        "requests": {
                            "memory": "128Mi",
                            "cpu": "250m"
                        }
                    },
                    "volumeMounts": [
                        {
                            "mountPath": "/share",
                            "name": "shared-volume"
                        },
                        {
                            "mountPath": "/etc/swift",
                            "name": "swift-credentials",
                            "readOnly": True
                        }
                    ]
                }
            ]

            d_job['spec']['template']['spec']['containers'].append({
                "name": "publish",
                "image": "fnndsc/pman-swift-publisher",
                "env": [
                    {
                        "name": "SWIFT_KEY",
                        "value": name
                    },
                    {
                        "name": "KUBECFG_PATH",
                        "value": "/tmp/.kube/config"
                    },
                    {
                        "name": "OPENSHIFTMGR_PROJECT",
                        "value": self.project
                    }
                ],
                "command": [
                    "python3",
                    "watch.py"
                ],
                "resources": {
                    "limits": {
                        "memory": "1024Mi",
                        "cpu": "2000m"
                    },
                    "requests": {
                        "memory": "128Mi",
                        "cpu": "250m"
                    }
                },
                "volumeMounts": [
                    {
                        "mountPath": "/share",
                        "name": "shared-volume"
                    },
                    {
                        "mountPath": "/etc/swift",
                        "name": "swift-credentials",
                        "readOnly": True
                    },
                    {
                        "name": "kubecfg-volume",
                        "mountPath": "/tmp/.kube/",
                        "readOnly": True
                    },
                ]
            })
            d_job['spec']['template']['spec']['volumes'] = [
                {
                    "name": "shared-volume",
                    "emptyDir": {
                    }
                },
                {
                    "name": "swift-credentials",
                    "secret": {
                        "secretName": "swift-credentials"
                    }
                },
                {
                    "name": "kubecfg-volume",
                    "secret": {
                        "secretName": "kubecfg"
                    }
                }
            ]
        else: # os.environ.get('STORAGE_TYPE') == 'hostPath'
            d_job['spec']['template']['spec']['volumes'] = [
                {
                    "name": "shared-volume",
                    "hostPath": {
                        "path": "/tmp/share/key-" + name
                    }
                }
            ]

        job = self.kube_v1_batch_client.create_namespaced_job(namespace=self.project, body=d_job)
        return job

    def create_pod(self, image, name):
        """
        Create a pod
        """
        pod_str = """
apiVersion: v1
kind: Pod
metadata:
    name: {name}
spec:
    restartPolicy: Never
    containers:
    - name: {name}
      image: {image}
""".format(name=name, image=image)

        pod_yaml = yaml.load(pod_str)
        pod = self.kube_client.create_namespaced_pod(namespace=self.project, body=pod_yaml)
        return pod

    def get_pod_status(self, name):
        """
        Get a pod's status
        """
        log = self.kube_client.read_namespaced_pod_status(namespace=self.project, name=name)
        return log

    def get_pod_log(self, name, container_name=None):
        """
        Get a pod log
        """
        if container_name:
            log = self.kube_client.read_namespaced_pod_log(namespace=self.project, name=name, container=container_name)
        else:
            log = self.kube_client.read_namespaced_pod_log(namespace=self.project, name=name)
        return log

    def get_job(self, name):
        """
        Get the previously scheduled job object
        """
        return self.kube_v1_batch_client.read_namespaced_job(name, self.project)

    def remove_job(self, name):
        """
        Remove a previously scheduled job
        """
        self.kube_v1_batch_client.delete_namespaced_job(name, self.project, {})

    def remove_pod(self, name):
        """
        Remove a previously scheduled pod
        """
        self.kube_client.delete_namespaced_pod(name, self.project, {})

    def state(self, name):
        """
        Return the state of a previously scheduled job
        """
        job = self.get_job(name)
        message = None
        state = None
        reason = None
        if job.status.conditions:
            for condition in job.status.conditions:
                if condition.type == 'Failed' and condition.status == 'True':
                    message = 'started'
                    reason = condition.reason
                    state = 'failed'
                    break
        if not state:
            if job.status.completion_time and job.status.succeeded > 0:
                message = 'finished'
                state = 'complete'
            elif job.status.active > 0:
                message = 'started'
                state = 'running'
            else:
                message = 'inactive'
                state = 'inactive'

        return {'Status': {'Message': message,
                                'State': state,
                                'Reason': reason,
                                'Active': job.status.active,
                                'Failed': job.status.failed,
                                'Succeeded': job.status.succeeded,
                                'StartTime': str(job.status.start_time),
                                'CompletionTime': str(job.status.completion_time)}}

    def get_job_pod_logs(self, pod_name):
        """
        Returns the concatenated log of all 3 containers part of job template.
        :param str pod_name: job-id of OpenShift job.  
        :return: str log: Combined log of all the containers in pod.
        """
        # Assumption is pod is always going to have a init-storage, container with job-id, publish container.
        # TODO: @ravig: Think of a better way to abstract out logs in case of multiple pods running parallelly.
        init_container_log = self.get_pod_log(pod_name, 'init-storage')
        # job-id is pod_name.split('-')[0]
        plugin_container = pod_name.split('-')[0]
        job_container_log = self.get_pod_log(pod_name, plugin_container)
        publish_container_log = self.get_pod_log(pod_name, 'publish')
        return pod_name + ":" + "init_container log:" + init_container_log + "plugin_container log:" +\
               job_container_log + "publish_container log:" + publish_container_log

    def get_pod_names_in_job(self, job_id):
        """
        Returns names of all the pods created as part of job
        :param str job_id: job-id of OpenShift job
        :return: 
        """
        pod_names = []
        # job-name becomes selector based on which we can choose jobs that we created just now.
        pods = self.kube_client.list_namespaced_pod(self.project, label_selector='job-name='+job_id)
        for _, pod_item in enumerate(pods.items):
            pod_names.append(pod_item.metadata.name)
        return pod_names
