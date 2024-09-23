#!/usr/bin/env bash

set -eu

sudo() {
  echo -n "Trying to run: sudo" 1>&2
  printf " %q" "$@" 1>&2
  echo 1>&2
  read -rp "Is that ok? [yn]: " yn 1>&2 </dev/tty
  case "$yn" in
    [Yy]*)
      command sudo "$@"
      ;;
    *)
      echo "Ok. Exiting..." 1>&2
      exit 1
      ;;
  esac
}

cleanup() {
  set -x +e

  if [[ -n "${IMAGE_BOOT_MNT:-}" ]]; then
    command sudo umount "$IMAGE_BOOT_MNT"
  fi

  if [[ -n "${IMAGE_ROOT_MNT:-}" ]]; then
    command sudo umount "$IMAGE_ROOT_MNT"
  fi

  if [[ -n "${LOOP_DEV:-}" ]]; then
    command sudo losetup -d "$LOOP_DEV"
  fi

  if [[ -n "${DEV_AUTO_BOOT_MOUNT:-}" ]]; then
    command sudo umount "$DEV_AUTO_BOOT_MOUNT"
  fi

  if [[ -n "${DEV_BOOT_MOUNT:-}" ]]; then
    command sudo umount "$DEV_BOOT_MOUNT"
  fi

  if [[ -n "${DEV_ROOT_MOUNT:-}" ]]; then
    command sudo umount "$DEV_ROOT_MOUNT"
  fi

  if [[ -n "${TMP_DIR:-}" ]]; then
    rm --one-file-system -rf "$TMP_DIR"
  fi
}

usage() {
  cat 1>&2 <<END
Usage: $0 [-p password] <image> <dev>
  -p Use specified password instead of generating a random one. ("-" to read from stdin)
END
  exit 1
}

patch_firstboot_resize_script() {
  if [[ "$#" -ne 1 ]]; then
    echo "patch_firstboot_resize_script expected one argument: <resize_script>"
    exit 1
  fi

  if ! sha256sum --status -c - <<<"0a86e750ad810b87a323c8e42ef76174110cb0338faf378c80d9fc6b6f87093b $1"; then
    echo "Failed to patch unknown version of '$1' file." 1>&2
    exit 1
  fi

  sudo patch -s "$1" <<END
34,38d33
<   if ! parted -m "\$ROOT_DEV" u s resizepart "\$ROOT_PART_NUM" "\$TARGET_END"; then
<     FAIL_REASON="Partition table resize of the root partition (\$DEV) failed\\n\$FAIL_REASON"
<     return 1
<   fi
< 
END
}

unpack_initramfs() {
  if [[ "$#" -ne 2 ]]; then
    echo "unpack_initramfs expects 2 arguments: <src> <unpack_dir>"
    exit 1
  fi

  unzstd --stdout "$1" | cpio -D "$2" -idmv --no-absolute-filenames 2>/dev/null
}

repack_initramfs() {
  if [[ "$#" -ne 2 ]]; then
    echo "repack_initramfs expects 2 arguments: <unpack_dir> <target>"
    exit 1
  fi

  local tmp_target
  tmp_target="$tmp_unpack/$(basename "$2").cpio"
  { cd "$1" && find .; } | cpio -D "$1" -ocR root:root 2>/dev/null | zstd -9 -o "$tmp_target"
  sudo mv -i "$tmp_target" "$2"
}

configure_user() {
  if [[ -z "${password:-}" ]]; then
    password="$(openssl rand -base64 40)"
    echo "Generated password: $password"
  fi

  local pw_hash
  pw_hash="$(openssl passwd -6 "$password")"

  echo "pi:$pw_hash" | sudo tee "$DEV_BOOT_MOUNT/userconf.txt" >/dev/null
}

enable_sshd() {
  sudo touch "$DEV_BOOT_MOUNT/ssh"
}

create_tmp_dir() {
  TMP_DIR="$(mktemp -d)"
}

mount_image() {
  LOOP_DEV="$(sudo losetup -PLrf --show "$1")"
  IMAGE_BOOT_MNT="$TMP_DIR/image_boot"
  IMAGE_ROOT_MNT="$TMP_DIR/image_root"
  mkdir "$IMAGE_BOOT_MNT"
  mkdir "$IMAGE_ROOT_MNT"

  sudo mount -o nodev,noexec,nosuid,ro "${LOOP_DEV}p1" "$IMAGE_BOOT_MNT"
  sudo mount -o nodev,noexec,nosuid,ro "${LOOP_DEV}p2" "$IMAGE_ROOT_MNT"
}

mount_dev() {
  DEV_AUTO_BOOT_MOUNT="$TMP_DIR/dev_autoboot"
  DEV_BOOT_MOUNT="$TMP_DIR/dev_boot"
  DEV_ROOT_MOUNT="$TMP_DIR/dev_root"

  mkdir "$DEV_AUTO_BOOT_MOUNT"
  mkdir "$DEV_BOOT_MOUNT"
  mkdir "$DEV_ROOT_MOUNT"

  #sudo mount -o nodev,nosuid,noexec "$(lsblk -po KNAME -n "$1" | grep -v "^$1$" | sedd)" "$DEV_AUTO_BOOT_MOUNT"
  get_partition "$1" 1
  sudo mount -o nodev,nosuid,noexec "$PART" "$DEV_AUTO_BOOT_MOUNT"
  get_partition "$1" 2
  sudo mount -o nodev,nosuid,noexec "$PART" "$DEV_BOOT_MOUNT"
  get_partition "$1" 5
  sudo mount -o nodev,nosuid,noexec "$PART" "$DEV_ROOT_MOUNT"
}

get_partition() {
  PART="$(lsblk -po KNAME -n "$1" | grep -v "^$1$" | sed -n "$2p")"
}

get_ptuuid() {
  PTUUID="$(lsblk -o PTUUID -n "$1" | head -1)"
}

format_dev() {
  total_size=$(lsblk -snbo size "$1")
  size=$(((total_size - 3 * 512 * 2**20 - 2 * 2048) / 2 / 1024))
  sudo sfdisk "$1" <<END
label: dos
unit: sectors

-, 512MiB, 0x0c, -
-, 512MiB, 0x0c, -
-, 512MiB, 0x0c, -
-, -, 0x05, -
-, ${size}KiB, 0x83, -
-, -, 0x83, -
END

  # Required because for e.g. loop devices
  # sfdisk's ioctl to reread partitions fails.
  sudo partprobe "$1"

  get_partition "$1" 1
  sudo mkfs.vfat -F 32 -n bootfs "$PART"
}

copy_to_dev() {
  get_partition "$1" 2
  sudo dd if="${LOOP_DEV}p1" of="$PART" bs=4M conv=fsync oflag=direct status=progress
  get_partition "$1" 5
  sudo dd if="${LOOP_DEV}p2" of="$PART" bs=4M conv=fsync oflag=direct status=progress
}

update_config() {
  sudo tee "$DEV_AUTO_BOOT_MOUNT/autoboot.txt" >/dev/null <<END
[all]
tryboot_a_b=1
boot_partition=2
[tryboot]
boot_partition=3
END

  get_ptuuid "$1"
  sudo sed -i -E "s/root=PARTUUID=[-[:alnum:]]+/root=PARTUUID=${PTUUID}-05/" "$DEV_BOOT_MOUNT/cmdline.txt"
  sudo gawk -i inplace -f - -F ' ' "$DEV_ROOT_MOUNT/etc/fstab" <<END
!/^ *#/ && (\$2 == "/" || \$2 == "/boot/firmware") {
  if (\$2 == "/")
    r=gsub(/PARTUUID=[-[:alnum:]]+/, "PARTUUID=${PTUUID}-05", \$1)
  if (\$2 == "/boot/firmware")
    r=gsub(/PARTUUID=[-[:alnum:]]+/, "PARTUUID=${PTUUID}-02", \$1)
  if (r != 1) {
    print "Failed to replace partition UUID in line: " \$0 >/dev/stderr
    exit 1
  }
}

{ print }
END
}

update_initramfs() {
  tmp_unpack="$TMP_DIR/initramfs_unpack"
  mkdir "$tmp_unpack"

  for f in "$DEV_BOOT_MOUNT"/initramfs*; do
    echo "Patching: $f"
    unpack_dir="$tmp_unpack/$(basename "$f")"
    mkdir "$unpack_dir"
    unpack_initramfs "$f" "$unpack_dir"
    patch_firstboot_resize_script "$unpack_dir/scripts/local-premount/firstboot"
    repack_initramfs "$unpack_dir" "$f"
  done
  patch_firstboot_resize_script "$DEV_ROOT_MOUNT/usr/share/initramfs-tools/scripts/local-premount/firstboot"
}

if [[ "${DEBUG:-0}" -ne 0 ]]; then
  set -x
fi

while getopts "p:" arg; do
  case "$arg" in
    p)
      if [[ "$OPTARG" = "-" ]]; then
        read -r password
      else
        password="$OPTARG"
      fi
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

unset TMP_DIR
trap 'cleanup' EXIT
create_tmp_dir
mount_image "$1"
format_dev "$2"
copy_to_dev "$2"
mount_dev "$2"
update_config "$2"
update_initramfs

echo "Creating userconf.txt ..." 1>&2
configure_user

echo "Enabling SSH access ..." 1>&2
enable_sshd
