# Watchtower: Edge Device Automation for Vessel Data Transmission

This Ansible project automates the configuration of edge devices deployed on vessels, enabling them to securely transmit data to an onshore SOC and gateway. It leverages Ansible roles for managing system services, network configurations, and security settings.

## Features

*   **Automated Cluster Setup:** Rapidly configure multiple edge devices.
*   **Secure Data Transmission:** Ensures data is sent securely to onshore systems.
*   **Network Configuration:** Manages essential network services including firewalling, SSH, and DNS resolution.
*   **Centralized Logging:** Configures rsyslog for efficient log management and forwarding.
*   **Secure Access:** Hardens SSH configurations for secure remote access.

## Roles

The following Ansible roles are utilized:

*   `rsyslog`: Configures and manages the rsyslog service for log collection and forwarding.
*   `sshd`: Manages the OpenSSH daemon, ensuring secure access.
*   `firewalld`: Configures the host-based firewall to allow necessary traffic and enhance security.
*   `ifupdown`: Manages network interface configurations.
*   `resolv_hosts`: Configures DNS resolution settings.

## Getting Started

### Prerequisites

*   Ansible installed on the control machine.
*   SSH access to the target edge devices.
*   (Potentially) Vault password for encrypted variables.

### Usage

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd watchtower
    ```

2.  **Define your inventory:** Update the `hosts` file with the target edge devices.

3.  **Configure variables:** Adjust settings in `vars_common_all.yml` and any role-specific variable files as needed. Pay close attention to network configurations, security settings, and data transmission parameters.

4.  **Run the playbook:**
    ```bash
    ansible-playbook -i hosts site.yml
    ```
    (Assuming `site.yml` is the main playbook orchestrating the roles).

## Configuration

### SSH Security

The `sshd` role can be configured via `vars_common_all.yml` or role-specific variables to enforce strong security practices, such as disabling root login, enabling key-based authentication, and setting appropriate log levels.

### Firewall Rules

The `firewalld` role allows defining specific ports and services to be opened for communication with the onshore gateway. Review `vars_common_all.yml` for examples of zone and rule configurations.

### Data Transmission

*   **Rsyslog:** Configure `rsyslog_remote` in `defaults/main.yml` (within the `rsyslog` role) to forward logs to the onshore SOC.
*   **Secure Tunneling:** The `notes.md` file contains references to WireGuard configurations, suggesting that a secure tunnel might be established for data exfiltration. Ensure these parameters are correctly set up if WireGuard is used.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
