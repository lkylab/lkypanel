#!/usr/bin/env bats
# Tests for mariadb install.sh and remove.sh

setup() {
    # Temp dirs for flag and log
    export FLAG_DIR="$(mktemp -d)"
    export LOG_FILE="$(mktemp)"

    # Stub system commands
    apt-get()  { echo "apt-get $*"; }
    yum()      { echo "yum $*"; }
    systemctl(){ echo "systemctl $*"; }
    ufw()      { echo "ufw $*"; }
    command()  {
        if [[ "$2" == "apt-get" ]]; then return 0; fi
        return 1
    }
    export -f apt-get yum systemctl ufw command

    INSTALL_SH="$(dirname "$BATS_TEST_FILENAME")/../../plugins/mariadb/install.sh"
    REMOVE_SH="$(dirname "$BATS_TEST_FILENAME")/../../plugins/mariadb/remove.sh"
}

teardown() {
    rm -rf "$FLAG_DIR"
    rm -f "$LOG_FILE"
}

@test "mariadb install.sh creates flag file on success" {
    FLAG_FILE="$FLAG_DIR/mariadb"
    FLAG_DIR="$FLAG_DIR" FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$INSTALL_SH"
    [ -f "$FLAG_FILE" ]
}

@test "mariadb install.sh writes [200] on success" {
    FLAG_FILE="$FLAG_DIR/mariadb"
    FLAG_DIR="$FLAG_DIR" FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$INSTALL_SH"
    grep -q '\[200\]' "$LOG_FILE"
}

@test "mariadb install.sh is idempotent (second run exits 0, no package manager call)" {
    FLAG_FILE="$FLAG_DIR/mariadb"
    touch "$FLAG_FILE"
    # Override apt-get to fail if called
    apt-get() { echo "apt-get called unexpectedly"; return 1; }
    export -f apt-get
    FLAG_DIR="$FLAG_DIR" FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$INSTALL_SH"
    [ $? -eq 0 ]
}

@test "mariadb install.sh writes [404] on failure" {
    FLAG_FILE="$FLAG_DIR/mariadb"
    # Make apt-get fail
    apt-get() { return 1; }
    export -f apt-get
    FLAG_DIR="$FLAG_DIR" FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$INSTALL_SH" || true
    grep -q '\[404\]' "$LOG_FILE"
}

@test "mariadb remove.sh deletes flag file on success" {
    FLAG_FILE="$FLAG_DIR/mariadb"
    touch "$FLAG_FILE"
    FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$REMOVE_SH"
    [ ! -f "$FLAG_FILE" ]
}

@test "mariadb remove.sh writes [200] on success" {
    FLAG_FILE="$FLAG_DIR/mariadb"
    touch "$FLAG_FILE"
    FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$REMOVE_SH"
    grep -q '\[200\]' "$LOG_FILE"
}

@test "mariadb remove.sh is idempotent when not installed" {
    FLAG_FILE="$FLAG_DIR/mariadb"
    # No flag file — should exit 0
    FLAG_FILE="$FLAG_FILE" LOG_FILE="$LOG_FILE" bash "$REMOVE_SH"
    [ $? -eq 0 ]
}
