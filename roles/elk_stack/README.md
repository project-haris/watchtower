# Ansible Role: ELK Stack

## Description

This role deploys a complete ELK (Elasticsearch, Logstash, Kibana) stack on Debian-based systems. It handles repository setup, package installation, and configuration for all three components.

## Requirements

### Platform
- **OS**: Debian/Ubuntu (uses apt)
- **Architecture**: x86_64 or aarch64
- **Hardware**: 4GB+ RAM recommended (8GB+ for production)

### Controller Node
- Ansible >= 2.10

## Role Structure

- `tasks/main.yml`: Main task file that installs and configures all ELK components
- `defaults/main.yml`: Default configuration variables
- `handlers/main.yml`: Service restart handlers
- `templates/`: Jinja2 templates for configuration files

## Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `elasticsearch_version` | `"8.x"` | Elastic stack major version |
| `elasticsearch_heap_size` | `"2g"` | JVM heap size (e.g., `2g`, `4g`) |
| `elastic_network_host` | `"0.0.0.0"` | Network bind address |
| `kibana_server_host` | `"0.0.0.0"` | Kibana bind address |
| `kibana_port` | `5601` | Kibana web interface port |
| `logstash_conf_dir` | `"/etc/logstash/conf.d"` | Logstash pipeline config directory |
| `elasticsearch_cluster_name` | `"elk-cluster"` | Elasticsearch cluster name |
| `elasticsearch_node_name` | `"node-01"` | Elasticsearch node name |
| `elasticsearch_security_enabled` | `false` | Enable X-Pack security |

## Dependencies

None.

## Example Playbook

```yaml
---
- name: Deploy ELK Stack
  hosts: elk_servers
  become: yes
  roles:
    - elk_stack
```

## Example Configuration

Create a `host_vars` file to customize the deployment:

**`inventory/host_vars/elk-server.yml`**
```yaml
---
elasticsearch_version: "8.x"
elasticsearch_heap_size: "4g"
elasticsearch_cluster_name: "production-cluster"
elasticsearch_node_name: "elk-node-01"
kibana_port: 5601
```

## Usage

1. Add the role to your `roles/` directory
2. Configure variables in `host_vars` or `group_vars`
3. Run the playbook:
   ```bash
   ansible-playbook -i inventory/hosts site.yml
   ```

## Post-Deployment Verification

1. **Check Services**:
   ```bash
   sudo systemctl status elasticsearch
   sudo systemctl status logstash
   sudo systemctl status kibana
   ```

2. **Access Dashboards**:
   - **Kibana**: `http://<host>:5601`
   - **Elasticsearch API**: `http://<host>:9200`

3. **Test Elasticsearch**:
   ```bash
   curl http://localhost:9200
   ```

## Security Notes

- By default, X-Pack security is disabled for simplicity
- For production, set `elasticsearch_security_enabled: true` and configure SSL/TLS
- Override default passwords and restrict network bindings as needed

## License

MIT
