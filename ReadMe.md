# openstack-iac

Infrastructure as Code проект для автоматического развертывания виртуальных машин и Kubernetes-кластеров в OpenStack.

Проект объединяет Terraform, Python-скрипты и Ansible playbook’и для полного цикла подготовки инфраструктуры:

* создание виртуальных машин в OpenStack;
* описание VM и Kubernetes-нод через YAML-файлы;
* автоматическое создание security groups, портов и floating IP;
* генерация Ansible inventory для Kubernetes-кластеров;
* настройка Kubernetes control-plane и worker-нод через Ansible;
* добавление новых worker-нод в существующий кластер.

## Стек технологий

* **OpenStack** — облачная платформа для запуска виртуальных машин;
* **Terraform** — описание и создание инфраструктуры;
* **Ansible** — настройка серверов и Kubernetes-нод;
* **Kubernetes** — оркестрация контейнеров;
* **Python** — вспомогательные скрипты для генерации конфигураций;
* **YAML** — декларативное описание VM и кластеров.

## Структура репозитория

```text
.
├── Kubernetes/
│   ├── prod/
│   └── test/
├── ansible/
│   └── kubernetes/
│       ├── roles/
│       ├── add-worker.yml
│       ├── inventory.ini
│       └── playbook.yml
├── scripts/
│   ├── add_vm_request.py
│   └── generate_k8s_inventory.py
├── main.tf
├── outputs.tf
├── providers.tf
├── variables.tf
└── vm-requests.yaml
```

### Основные файлы

| Файл / каталог        | Назначение                                                                                         |
| --------------------- | -------------------------------------------------------------------------------------------------- |
| `main.tf`             | Основная Terraform-конфигурация для создания VM, портов, security groups и floating IP в OpenStack |
| `providers.tf`        | Настройка Terraform-провайдера OpenStack                                                           |
| `variables.tf`        | Переменные проекта, включая CIDR для административного доступа и приватной сети                    |
| `outputs.tf`          | Вывод информации о созданных VM: ID, имя, статус, private IP, floating IP и SSH-команда            |
| `vm-requests.yaml`    | YAML-файл с описанием обычных виртуальных машин                                                    |
| `Kubernetes/`         | Описания Kubernetes-кластеров и их нод                                                             |
| `ansible/kubernetes/` | Ansible playbook’и и роли для настройки Kubernetes                                                 |
| `scripts/`            | Python-скрипты для генерации VM-заявок и Ansible inventory                                         |

## Как это работает

### 1. Описание виртуальных машин

Обычные виртуальные машины описываются в файле `vm-requests.yaml`.

Пример:

```yaml
vms:
  dev-ubuntu-03:
    image: ubuntu-24.04
    flavor: m1.small
    network: private
    keypair: default-key
    floating_ip: false
    admin_cidr: 192.168.0.0/24
```

Terraform читает этот файл и создает соответствующие ресурсы в OpenStack.

### 2. Описание Kubernetes-кластеров

Kubernetes-ноды описываются в каталоге `Kubernetes/<cluster-name>/`.

Для каждого кластера могут использоваться файлы:

```text
Kubernetes/<cluster-name>/
├── cluster.yaml
├── control-plane-requests.yaml
└── worker-node-requests.yaml
```

Где:

* `cluster.yaml` — общие параметры Kubernetes-кластера;
* `control-plane-requests.yaml` — список control-plane нод;
* `worker-node-requests.yaml` — список worker-нод.

Terraform автоматически читает YAML-файлы из каталога `Kubernetes/` и добавляет control-plane и worker-ноды к общему списку создаваемых VM.

### 3. Создание инфраструктуры через Terraform

Перед запуском убедитесь, что у вас настроен доступ к OpenStack.

Обычно для этого используются OpenStack environment variables, например:

```bash
export OS_AUTH_URL=...
export OS_PROJECT_NAME=...
export OS_USERNAME=...
export OS_PASSWORD=...
export OS_REGION_NAME=...
export OS_USER_DOMAIN_NAME=...
export OS_PROJECT_DOMAIN_NAME=...
```

После настройки окружения выполните:

```bash
terraform init
terraform plan
terraform apply
```

После успешного выполнения Terraform создаст виртуальные машины и выведет информацию о них через `outputs.tf`.

## Использование Python-скриптов

### Добавление новой VM-заявки

Скрипт `scripts/add_vm_request.py` добавляет описание виртуальной машины в нужный YAML-файл.

Поддерживаемые типы VM:

* `base` — обычная виртуальная машина;
* `kubernetes-control-plane` — control-plane нода Kubernetes;
* `kubernetes-worker` — worker-нода Kubernetes.

Пример добавления обычной VM:

```bash
export VM_TYPE=base
export VM_NAME=dev-ubuntu-04
export VM_IMAGE=ubuntu-24.04
export VM_FLAVOR=m1.small
export VM_NETWORK=private
export VM_KEYPAIR=default-key
export VM_FLOATING_IP=false
export VM_ADMIN_CIDR=192.168.0.0/24

python3 scripts/add_vm_request.py
```

Пример добавления Kubernetes control-plane ноды:

```bash
export VM_TYPE=kubernetes-control-plane
export VM_NAME=k8s-test-control-01
export K8S_CLUSTER=test
export VM_IMAGE=ubuntu-24.04
export VM_FLAVOR=m1.medium
export VM_NETWORK=private
export VM_KEYPAIR=default-key
export VM_FLOATING_IP=true
export VM_ADMIN_CIDR=192.168.0.0/24

python3 scripts/add_vm_request.py
```

Пример добавления Kubernetes worker-ноды:

```bash
export VM_TYPE=kubernetes-worker
export VM_NAME=k8s-test-worker-01
export K8S_CLUSTER=test
export VM_IMAGE=ubuntu-24.04
export VM_FLAVOR=m1.medium
export VM_NETWORK=private
export VM_KEYPAIR=default-key
export VM_FLOATING_IP=true
export VM_ADMIN_CIDR=192.168.0.0/24

python3 scripts/add_vm_request.py
```

## Генерация Ansible inventory

Скрипт `scripts/generate_k8s_inventory.py` получает информацию о VM из OpenStack и генерирует inventory-файл для Ansible.

Пример:

```bash
python3 scripts/generate_k8s_inventory.py --cluster test
```

Inventory будет создан в каталоге:

```text
ansible/kubernetes/inventory/<cluster>.ini
```

Для генерации inventory только для конкретной worker-ноды:

```bash
python3 scripts/generate_k8s_inventory.py --cluster test --target-worker k8s-test-worker-01
```

## Настройка Kubernetes через Ansible

### Полная настройка кластера

Для подготовки всех Kubernetes-нод используется playbook:

```bash
ansible-playbook -i ansible/kubernetes/inventory/test.ini ansible/kubernetes/playbook.yml
```

Playbook выполняет три основных этапа:

1. Подготовка всех Kubernetes-нод через роль `common`;
2. Bootstrap control-plane нод через роль `control_plane`;
3. Подключение worker-нод через роль `worker`.

### Добавление worker-ноды

Для добавления новой worker-ноды в существующий кластер используется playbook `add-worker.yml`.

Пример:

```bash
ansible-playbook \
  -i ansible/kubernetes/inventory/test.ini \
  ansible/kubernetes/add-worker.yml \
  -e target_worker=k8s-test-worker-01
```

Playbook:

1. Подготавливает указанную worker-ноду;
2. Генерирует `kubeadm join` команду на control-plane ноде;
3. Подключает worker-ноду к Kubernetes-кластеру.

## Переменные Terraform

В проекте используются следующие переменные:

| Переменная            | Значение по умолчанию | Назначение                                                                    |
| --------------------- | --------------------: | ----------------------------------------------------------------------------- |
| `default_admin_cidr`  |      `192.168.0.0/24` | CIDR, которому разрешен административный доступ по SSH и ICMP                 |
| `private_subnet_cidr` |         `10.0.0.0/24` | Приватная подсеть для внутреннего взаимодействия между VM и Kubernetes-нодами |

## Outputs

После выполнения `terraform apply` Terraform выводит информацию о созданных виртуальных машинах:

* ID виртуальной машины;
* имя;
* статус;
* private IP;
* floating IP, если он был назначен;
* SSH-команду для подключения.

Пример:

```bash
terraform output vms
```

## Требования

Перед использованием проекта необходимо установить:

* Terraform `>= 1.6.0`;
* OpenStack CLI;
* Python 3;
* Ansible;
* Python-библиотеку `PyYAML`;
* доступ к OpenStack-проекту;
* SSH keypair, зарегистрированный в OpenStack.

Установка Python-зависимости:

```bash
pip install pyyaml
```

## Типовой workflow

```bash
# 1. Добавить описание VM или Kubernetes-ноды
python3 scripts/add_vm_request.py

# 2. Создать инфраструктуру в OpenStack
terraform init
terraform plan
terraform apply

# 3. Сгенерировать Ansible inventory для Kubernetes
python3 scripts/generate_k8s_inventory.py --cluster test

# 4. Настроить Kubernetes-кластер
ansible-playbook \
  -i ansible/kubernetes/inventory/test.ini \
  ansible/kubernetes/playbook.yml
```

## Удаление инфраструктуры

Для удаления созданных ресурсов выполните:

```bash
terraform destroy
```

## Безопасность

Не храните в репозитории:

* пароли от OpenStack;
* приватные SSH-ключи;
* токены доступа;
* kubeconfig-файлы с production-доступом;
* секреты Kubernetes.

Для чувствительных данных используйте переменные окружения, secret storage или CI/CD secrets.

## Назначение проекта

Этот репозиторий подходит для автоматизации инфраструктуры в OpenStack и ускорения развертывания Kubernetes-кластеров. Он позволяет описывать инфраструктуру декларативно, повторяемо создавать виртуальные машины и настраивать Kubernetes-ноды через Ansible.

[1]: https://github.com/thetatiana/openstack-iac "GitHub - thetatiana/openstack-iac · GitHub"
