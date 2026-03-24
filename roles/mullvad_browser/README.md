# Ansible Role: Mullvad Browser

## Description

This role installs Mullvad Browser using Mullvad's official Linux repositories.

For Debian-based hosts, the role follows Mullvad's documented apt repository setup:

- downloads the Mullvad signing key to `/usr/share/keyrings/mullvad-keyring.asc`
- writes `/etc/apt/sources.list.d/mullvad.list`
- refreshes the apt cache
- checks which browser package is available for the local architecture

For RedHat-family hosts, the role installs Mullvad's RPM repo file at `/etc/yum.repos.d/mullvad.repo`, refreshes DNF metadata, and then performs the same stable-first package selection.

The role prefers the stable package `mullvad-browser`. If the stable package is not published for the current architecture, it falls back to `mullvad-browser-alpha`.

## Requirements

- Debian, Ubuntu, Raspberry Pi OS, Fedora, or another RedHat-family system with `dnf`
- Network access to `repository.mullvad.net`

## Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `mullvad_browser_repository_url` | `"https://repository.mullvad.net/deb/stable"` | Mullvad apt repository base URL |
| `mullvad_browser_repository_component` | `"main"` | Apt repository component |
| `mullvad_browser_repository_suite` | `"stable"` | Apt repository suite |
| `mullvad_browser_rpm_repo_url` | `"https://repository.mullvad.net/rpm/stable/mullvad.repo"` | Mullvad RPM repository file URL |
| `mullvad_browser_keyring_path` | `"/usr/share/keyrings/mullvad-keyring.asc"` | Location of the Mullvad signing key |
| `mullvad_browser_keyring_url` | `"https://repository.mullvad.net/deb/mullvad-keyring.asc"` | URL for the Mullvad signing key |
| `mullvad_browser_package_name` | `"mullvad-browser"` | Preferred stable package name |
| `mullvad_browser_fallback_package_name` | `"mullvad-browser-alpha"` | Fallback package name when stable is not available |

## Package Selection

After the repository is added, the role checks package availability:

- on Debian-based hosts, with `apt-cache madison`
- on RedHat-family hosts, with `dnf list --showduplicates`

Then:

- if `mullvad-browser` exists, it is installed
- if `mullvad-browser` does not exist but `mullvad-browser-alpha` does, the alpha package is installed
- if neither package exists, the role fails with a clear error

This is useful on architectures where Mullvad does not currently publish the stable browser package but does publish an alpha build.

## Example Run

Run only the Mullvad Browser role on edge devices:

```bash
ansible-playbook playbooks/group_vessel_edge/main.yml -t mullvad_browser -D
```

## Notes

- This role follows Mullvad's official Debian/Ubuntu repository setup closely, but automates it in Ansible.
- Mullvad's current docs explicitly cover Debian/Ubuntu and Fedora. RedHat-family support beyond Fedora is a best-effort use of the published RPM repository.
- Once installed, the selected package upgrades through normal `apt` runs.
- On some architectures, the Mullvad repository may only provide `mullvad-browser-alpha` and not `mullvad-browser`.
