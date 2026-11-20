"""Verify the generated Nickey44A configuration and the application inside each UF2."""

import argparse
import hashlib
import struct
import sys
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_uf2(output, tree):
    uf2 = (output / "zmk.uf2").read_bytes()
    binary = (output / "zmk.bin").read_bytes()
    partition = tree.get_node("/chosen").props["zephyr,code-partition"].to_path()
    start, capacity = partition.props["reg"].to_nums()
    require((start, capacity) == (0x27000, 0xC5000), "unexpected XIAO application partition")
    require(0 < len(binary) <= capacity, "zmk.bin does not fit the application partition")

    count = (len(binary) + 255) // 256
    require(len(uf2) == count * 512, "UF2 size does not match zmk.bin")
    header = struct.Struct("<8I")
    for index in range(count):
        block = uf2[index * 512 : (index + 1) * 512]
        magic1, magic2, flags, address, size, number, total, family = header.unpack_from(block)
        require((magic1, magic2) == (0x0A324655, 0x9E5D5157)
                and struct.unpack_from("<I", block, 508)[0] == 0x0AB16F30,
                f"invalid UF2 signature at block {index}")
        require((flags, family) == (0x2000, 0xADA52840), f"wrong UF2 flags or family at block {index}")
        require((number, total, size) == (index, count, 256), f"invalid block metadata at {index}")
        offset = index * 256
        require(address == start + offset and address + size <= start + capacity,
                f"invalid application address at block {index}")
        expected = binary[offset : offset + size].ljust(size, b"\0")
        require(block[32 : 32 + size] == expected, f"payload differs from zmk.bin at block {index}")
    return hashlib.sha256(uf2).hexdigest()


def active_nodes(tree, compatible):
    def enabled(node):
        while node is not None:
            status = node.props.get("status")
            if status and status.to_string() != "okay":
                return False
            node = node.parent
        return True

    return [node for node in tree.node_iter() if "compatible" in node.props
            and compatible in node.props["compatible"].to_strings() and enabled(node)]


def cells(prop):
    # Mixed phandles and integer parameters are represented as big-endian cells.
    return [value for (value,) in struct.iter_unpack(">I", prop.value)]


def check_setting(config, name, expected):
    value = config.get("CONFIG_" + name, "n")
    require(value == expected, f"CONFIG_{name}: expected {expected}, found {value}")


def verify_pad(pad, tree, profile, side, config):
    ats = profile == "ats"
    rotation = 270 if side == "left" else 90
    check_setting(config, f"INPUT_IQS9151_ROTATE_{rotation}", "y")
    for name, expected in {
        "RESOLUTION_X": "1300", "RESOLUTION_Y": "1192",
        "CURSOR_INERTIA_ENABLE": "y" if ats else "n",
        "SCROLL_INERTIA_ENABLE": "n" if ats else "y",
        "2F_PINCH_ENABLE": "n",
        "SCROLL_X_ENABLE": "n" if ats and side == "right" else "y",
        "SCROLL_Y_ENABLE": "y",
    }.items():
        check_setting(config, "INPUT_IQS9151_" + name, expected)
    require(pad.parent is tree.label2node["i2c0"], "pad must be on I2C0")
    require(pad.props["reg"].to_nums() == [0x56], "wrong IQS9151 address")
    require(pad.parent.props["clock-frequency"].to_num() == 100000, "wrong I2C clock")
    for state in ("pinctrl-0", "pinctrl-1"):
        group = pad.parent.props[state].to_node().nodes["group1"]
        # nRF TWIM function selectors and pin numbers for SDA and SCL.
        expected_scl = 0xB000A if ats else 0xB0021
        require(group.props["psels"].to_nums() == [0xC0009, expected_scl], f"wrong pins in {state}")
    gpio = tree.label2node["gpio1" if ats else "gpio0"].props["phandle"].to_num()
    require(cells(pad.props["irq-gpios"]) == [gpio, 10 if ats else 15, 0x11],
            "wrong RDY GPIO, polarity or pull-up")
    require("rst-gpios" not in pad.props, "unexpected reset GPIO")


def verify_build(profile, side, build, dtlib):
    output = build / "zephyr"
    config = dict(line.split("=", 1) for line in (output / ".config").read_text().splitlines()
                  if line.startswith("CONFIG_") and "=" in line)
    tree = dtlib.DT(str(output / "zephyr.dts"))
    right = side == "right"
    expected_pad = right or profile == "ats"
    check_setting(config, "BOARD", '"seeeduino_xiao_ble"')
    check_setting(config, "ZMK_SPLIT", "y")
    check_setting(config, "ZMK_SPLIT_ROLE_CENTRAL", "y" if right else "n")
    check_setting(config, "ZMK_STUDIO", "y" if right else "n")
    check_setting(config, "INPUT_IQS9151", "y" if expected_pad else "n")
    pads = active_nodes(tree, "azoteq,iqs9151")
    require(len(pads) == int(expected_pad), f"unexpected number of active pads: {len(pads)}")
    if expected_pad:
        verify_pad(pads[0], tree, profile, side, config)

    splits = active_nodes(tree, "zmk,input-split")
    require(len(splits) == int(profile == "ats"), "wrong number of split input nodes")
    if splits:
        require(splits[0].props["reg"].to_nums() == [0], "unexpected split input ID")
        if not right:
            require(splits[0].props["device"].to_node() is pads[0], "wrong left pad split source")
    if right:
        check_setting(config, "ZMK_POINTING_SMOOTH_SCROLLING", "y")
        listeners = active_nodes(tree, "zmk,input-listener")
        devices = [node.props["device"].to_node() for node in listeners]
        for source in pads + splits:
            require(devices.count(source) == 1, f"expected one input listener for {source.path}")
    return verify_uf2(output, tree)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=["nix", "ats"])
    parser.add_argument("left_build", type=Path)
    parser.add_argument("right_build", type=Path)
    parser.add_argument("zephyr", type=Path, help="Zephyr source directory used for the build")
    args = parser.parse_args()
    sys.path.insert(0, str(args.zephyr / "scripts/dts/python-devicetree/src"))
    from devicetree import dtlib

    for side, build in (("left", args.left_build), ("right", args.right_build)):
        try:
            digest = verify_build(args.profile, side, build, dtlib)
        except (OSError, ValueError, KeyError, dtlib.DTError) as error:
            sys.exit(f"{args.profile}-{side}: {error}")
        print(f"{args.profile}-{side}.uf2: configuration and payload verified, SHA-256 {digest}")


if __name__ == "__main__":
    main()
