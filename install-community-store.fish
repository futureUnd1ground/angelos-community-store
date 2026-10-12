#!/usr/bin/env fish
# Fish entry point for the verified Python installer.

set -l installer_url https://raw.githubusercontent.com/futureUnd1ground/angelos-community-store/main/install-community-store.py
set -l installer (mktemp)
or begin
    echo "Could not create a temporary installer file." >&2
    exit 1
end

if not command -q curl
    echo "curl is required to download Community Store." >&2
    rm -f -- $installer
    exit 1
end

if not command -q python3
    echo "python3 is required to install Community Store." >&2
    rm -f -- $installer
    exit 1
end

curl -fsSL $installer_url -o $installer
if test $status -ne 0
    echo "Could not download the installer." >&2
    rm -f -- $installer
    exit 1
end

python3 $installer $argv
set -l install_status $status
rm -f -- $installer

if test $install_status -ne 0
    exit $install_status
end

if command -q fish_add_path
    fish_add_path $HOME/.local/bin
end

echo "Fish PATH configured. Run: community-store"
