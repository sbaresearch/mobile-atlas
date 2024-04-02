#!/usr/bin/env bash

set -eu

if [[ "${DEBUG:-0}" -ne 0 ]]; then
  set -x
fi

boot_mount='boot'
rootfs_mount='rootfs'

umount_dev() {
  trap 0

  set +e

  sudo umount "$boot_mount"
  sudo umount "$rootfs_mount"
  rmdir "$boot_mount"
  rmdir "$rootfs_mount"
  rmdir "$tmp_dir"

  set -e
}

mount_dev() {
  tmp_dir="$(mktemp -d)"
  boot_mount="$tmp_dir/$boot_mount"
  rootfs_mount="$tmp_dir/$rootfs_mount"

  trap 'umount_dev' 0

  mkdir "$boot_mount"
  mkdir "$rootfs_mount"

  sudo mount -o noexec,nodev,nosuid "$1" "$boot_mount"
  sudo mount -o noexec,nodev,nosuid "$2" "$rootfs_mount"
}

usage() {
  exec 1>&2

  printf 'Usage: %s: [-r size] [-p password] (-m <path to boot mount> <path to rootfs mount> | <boot part dev> <rootfs part dev>)\n' "$0"
  printf '\t-m Use already mounted filesystems instead of mounting them first.\n'
  printf '\t-p Use the specified password instead of generating one. (When "-" read from standard input.)\n'
  printf '\t-r Resize target in GiB.\n'

  exit 1
}

patch_firstboot_script() {
  path_resize_script="$rootfs_mount/usr/lib/raspberrypi-sys-mods/firstboot"

  if ! sha256sum --status -c - <<<"7a28d81fd01abe04d1a610e071d35d232140c2efe216b0125a715822d5e024b0 $path_resize_script"; then
    echo "Failed to patch unknown version of '/usr/lib/raspberrypi-sys-mods/firstboot' file." 1>&2
    exit 1
  fi

  # fix partition size to "$resize GiB" (overwrite target of partition in line 75)
  sudo patch -s "$path_resize_script" <<END
60a61
>   TARGET_END=\$((ROOT_PART_START + $(((resize * 2**30) / 512))))
END
}

configure_user() {
  if [[ -z "${password:-}" ]]; then
    password="$(openssl rand -base64 40)"
    echo "Generated password: $password"
  fi

  pw_hash="$(openssl passwd -6 "$password")"

  echo "pi:$pw_hash" | sudo tee "$boot_mount/userconf.txt" >/dev/null
}

enable_sshd() {
  sudo touch "$boot_mount/ssh"
}

mount=1
while getopts p:mr: arg; do
  case "$arg" in
    p)
      if [[ "$OPTARG" = "-" ]]; then
        read -r password
      else
        password="$OPTARG"
      fi
      ;;
    m)
      mount=0
      ;;
    r)
      # checks whether $OPTARG is an integer
      if ! [ "$OPTARG" -eq "$OPTARG" ]; then
        usage
      fi
      resize="$OPTARG"
      ;;
    ?)
      usage
      ;;
  esac
done

shift "$((OPTIND - 1))"

if [[ "$#" -ne 2 ]]; then
  usage
fi

if [[ "$mount" -eq 0 ]]; then
  boot_mount="$1"
  rootfs_mount="$2"
else
  echo "Mounting devices '$1' and '$2'..." 1>&2
  mount_dev "$1" "$2"
fi

if [[ -n "${resize:-}" ]]; then
  echo "Patching '/usr/lib/raspberrypi-sys-mods/firstboot' ..." 1>&2
  patch_firstboot_script
fi

echo "Creating userconf.txt ..." 1>&2
configure_user

echo "Enabling SSH access ..." 1>&2
enable_sshd
