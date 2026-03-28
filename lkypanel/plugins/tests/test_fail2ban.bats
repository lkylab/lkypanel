#!/usr/bin/env bats
# Tests for fail2ban install.sh and remove.sh

setup() {
    export FLAG_DIR="$(mktemp -d)"
    export LOG_FILE="$(mktemp)"
    apt-get()  { echo "apt-get $*"; }
    yum()      { echo "yum $*"; }
    systemctl(){ echo "systemctl $*"; }
    ufw()      { echo "ufw $*"; }
    command()  { if [[ "$2" == "apt-get" ]]; then return 0; fi; return 1; }
    export -f apt-get yum systemctl ufw command
    INSTALL_SH="$(dirname "$BATS_TEST_FILENAME")/../../plugins/fail2ban/install.sh"
    REMOVE_SH="$(dirname "$BATS_TEST_FILENAME")/../../plugins/fail2ban/remove.sh"
}

teardown() { rm -rf "$FLAG_DIR"; rm -f "$LOG_FILE"; }

@test "fail2ban install.sh creates flag file on success" {
    FLAG_FILE="$FLAG_DIR/fail2ban"
    FLAG_DIR="$FLAG_DIR" FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$INSTALL_SH"
    [ -f "$FLAG_FILE" ]
}

@test "fail2ban install.sh writes [200] on success" {
    FLAG_FILE="$FLAG_DIR/fail2ban"
    FLAG_DIR="$FLAG_DIR" FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$INSTALL_SH"
    grep -q '\[200\]' "$LOG_FILE"
}

@test "fail2ban install.sh is idempotent" {
    FLAG_FILE="$FLAG_DIR/fail2ban"
    touch "$FLAG_FILE"
    apt-get() { return 1; }; export -f apt-get
    FLAG_DIR="$FLAG_DIR" FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$INSTALL_SH"
    [ $? -eq 0 ]
}

@test "fail2ban install.sh writes [404] on failure" {
    FLAG_FILE="$FLAG_DIR/fail2ban"
    apt-get() { return 1; }; export -f apt-get
    FLAG_DIR="$FLAG_DIR" FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$INSTALL_SH" || true
    grep -q '\[404\]' "$LOG_FILE"
}

@test "fail2ban remove.sh deletes flag file on success" {
    FLAG_FILE="$FLAG_DIR/fail2ban"
    touch "$FLAG_FILE"
    FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$REMOVE_SH"
    [ ! -f "$FLAG_FILE" ]
}

@test "fail2ban remove.sh writes [200] on success" {
    FLAG_FILE="$FLAG_DIR/fail2ban"
    touch "$FLAG_FILE"
    FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$REMOVE_SH"
    grep -q '\[200\]' "$LOG_FILE"
}

@test "fail2ban remove.sh is idempotent when not installed" {
    FLAG_FILE="$FLAG_DIR/fail2ban"
    FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$REMOVE_SH"
    [ $? -eq 0 ]
}
