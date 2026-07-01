"""
IPv6 Toolkit
------------
A dark-themed desktop GUI with several IPv6/IPv4 tools, selectable from the
Tools menu. Each tool swaps the input row and shares one output box. The "≡"
menu prints reference info into that same output box (no pop-up windows).

Tools menu (alphabetical):
    Embed IPv4 in Prefix     - place an IPv4 into an IPv6 prefix's low 32 bits,
                               shown in hex and dotted-IPv4 forms (+ doc example)
    IPv4 Calculator          - IPv4 subnet details from address/prefix
    IPv4 → Hex               - IPv4 as hex octets (c0:a8:01:01), packed, 0x, decimal
    IPv4-in-IPv6 Embeddings  - how an IPv4 address is embedded in IPv6: NAT64
                               (current) and IPv4-mapped, plus the deprecated
                               6to4 and IPv4-compatible forms (not a real
                               conversion -- dual-stack is the modern answer)
    IPv6 Calculator          - IPv6 network/first/last/count from address/prefix
    Prefix Converter         - prefix <-> count/mask, and compressed <-> exploded
    Random Address Generator - random host-in-prefix (blank = global unicast
                               2000::/4), documentation (2001:db8::/32), or
                               ULA (fd00::/8)
"""

import ipaddress
import random
import tkinter as tk

import customtkinter as ctk

APP_TITLE = "IPv6 Toolkit"
VERSION = "0.7.0 (alpha release)"
GITHUB_URL = "https://github.com/confignomad/ipv6-toolkit"

# Only enumerate individual hosts when a network is this small or smaller.
MAX_ENUMERATE = 1024
# Cap on how many random addresses one click may generate.
MAX_RANDOM = 100

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ----------------------------------------------------------------------------
# Pure logic (no GUI) -- each returns a dict; an "error" key means failure.
# ----------------------------------------------------------------------------
def calculate_ipv6(text):
    """IPv6 subnet details for an 'address/prefix' string. Never iterates."""
    text = text.strip()
    if not text:
        return {"error": "Enter an IPv6 address with a prefix, e.g. 2001:db8::/32"}
    if "/" not in text:
        return {"error": "Missing prefix. Use CIDR form, e.g. 2001:db8::/64"}
    try:
        net = ipaddress.ip_network(text, strict=False)
    except ValueError as e:
        return {"error": f"Invalid IPv6 network: {e}"}
    if net.version != 6:
        return {"error": "That is an IPv4 address. Use the IPv4 Calculator tool."}
    return {
        "network": net.network_address.compressed,
        "first": net[0].compressed,
        "last": net[-1].compressed,
        "prefixlen": net.prefixlen,
        "num_addresses": net.num_addresses,
        "compressed": net.compressed,
        "exploded": net.exploded,
    }


def calculate_ipv4(text):
    """IPv4 subnet details for an 'address/prefix' string."""
    text = text.strip()
    if not text:
        return {"error": "Enter an IPv4 address with a prefix, e.g. 192.168.1.0/24"}
    if "/" not in text:
        return {"error": "Missing prefix. Use CIDR form, e.g. 192.168.1.0/24"}
    try:
        net = ipaddress.ip_network(text, strict=False)
    except ValueError as e:
        return {"error": f"Invalid IPv4 network: {e}"}
    if net.version != 4:
        return {"error": "That is an IPv6 address. Use the IPv6 Calculator tool."}
    total = net.num_addresses
    if net.prefixlen >= 31:           # /31 point-to-point, /32 single host
        usable, first_host, last_host = total, net[0], net[-1]
    else:
        usable, first_host, last_host = total - 2, net[1], net[-2]
    return {
        "network": str(net.network_address),
        "broadcast": str(net.broadcast_address),
        "netmask": str(net.netmask),
        "wildcard": str(net.hostmask),
        "prefixlen": net.prefixlen,
        "total": total,
        "usable": usable,
        "first_host": str(first_host),
        "last_host": str(last_host),
    }


def random_address(kind, prefix_text=""):
    """Return one random address of the requested kind. Never iterates."""
    try:
        if kind == "Host in prefix":
            t = prefix_text.strip()
            if not t:                       # prefix optional -- blank = global unicast
                net = ipaddress.ip_network("2000::/4")
                scope = "blank prefix -> global unicast (2000::/4)"
            else:
                if "/" not in t:
                    return {"error": "Enter a network with prefix, e.g. 2001:db8::/64"}
                net = ipaddress.ip_network(t, strict=False)
                if net.version != 6:
                    return {"error": "Enter an IPv6 network, e.g. 2001:db8::/64"}
                scope = f"within {net.compressed}"
        elif kind == "Documentation":
            # Documentation range (RFC 3849) -- reserved for examples, never routed.
            net = ipaddress.ip_network("2001:db8::/32")
            scope = "documentation range (2001:db8::/32, RFC 3849)"
        elif kind == "ULA":
            net = ipaddress.ip_network("fd00::/8")
            scope = "unique local (fd00::/8)"
        else:
            return {"error": f"Unknown generator type: {kind}"}
    except ValueError as e:
        return {"error": str(e)}
    idx = random.randrange(net.num_addresses)   # handles 128-bit ranges
    return {"address": net[idx].compressed, "scope": scope}


def convert_prefix_length(text):
    """Prefix length -> address count, hex netmask, and /64 subnet count."""
    t = text.strip().lstrip("/")
    if not t.isdigit():
        return {"error": "Enter a prefix length 0-128, e.g. 64"}
    p = int(t)
    if not 0 <= p <= 128:
        return {"error": "Prefix length must be 0-128"}
    mask_int = ((1 << 128) - (1 << (128 - p))) if p > 0 else 0
    return {
        "prefix": p,
        "count": 2 ** (128 - p),
        "mask": ipaddress.IPv6Address(mask_int).exploded,
        "subnets64": 2 ** (64 - p) if p <= 64 else None,
    }


def convert_address_form(text):
    """Show both compressed and exploded forms of an IPv6 address."""
    t = text.strip().split("/")[0]
    try:
        a = ipaddress.IPv6Address(t)
    except ValueError as e:
        return {"error": f"Invalid IPv6 address: {e}"}
    return {"compressed": a.compressed, "exploded": a.exploded}


def ipv4_to_hex(text):
    """Convert an IPv4 address to hexadecimal forms (colon, packed, 0x, decimal)."""
    t = text.strip()
    if not t:
        return {"error": "Enter an IPv4 address, e.g. 192.168.1.1"}
    try:
        v4 = ipaddress.IPv4Address(t)
    except ValueError as e:
        return {"error": f"Invalid IPv4 address: {e}"}
    iv = int(v4)
    octets = [format(b, "02x") for b in v4.packed]
    return {
        "ipv4": str(v4),
        "colon": ":".join(octets),      # e.g. c0:a8:01:01 (matches IP4tohex.py)
        "packed": "".join(octets),      # e.g. c0a80101
        "hexint": f"0x{iv:08X}",        # e.g. 0xC0A80101
        "decimal": iv,                  # e.g. 3232235777
    }


def ipv4_to_ipv6(text):
    """Represent an IPv4 address in IPv6 forms (mapped, 6to4, compatible)."""
    t = text.strip()
    try:
        v4 = ipaddress.IPv4Address(t)
    except ValueError as e:
        return {"error": f"Invalid IPv4 address: {e}"}
    iv = int(v4)
    nat64_base = int(ipaddress.IPv6Address("64:ff9b::"))
    return {
        "ipv4": str(v4),
        "nat64": ipaddress.IPv6Address(nat64_base + iv).compressed,
        "mapped": ipaddress.IPv6Address(iv + 0xFFFF00000000).compressed,
        "sixto4": ipaddress.IPv6Address((0x2002 << 112) + (iv << 80)).compressed + "/48",
        "compat": ipaddress.IPv6Address(iv).compressed,
    }


def _ipv6_mixed(combined, v4):
    """Render an IPv6 address with its low 32 bits written as dotted IPv4.

    e.g. fd2b:1a9c:7e3f::ac1f:1001  ->  fd2b:1a9c:7e3f::172.31.16.1
    Compresses the longest run of zero groups, then verifies the result
    parses back to the same address (falling back to uncompressed if not).
    """
    groups = combined.exploded.split(":")[:6]          # leading 96 bits
    start, length, i = -1, 0, 0
    while i < 6:                                        # find longest zero run
        if groups[i] == "0000":
            j = i
            while j < 6 and groups[j] == "0000":
                j += 1
            if j - i > length:
                start, length = i, j - i
            i = j
        else:
            i += 1
    disp = [g.lstrip("0") or "0" for g in groups]
    if length >= 1:
        left, right = disp[:start], disp[start + length:]
        head = ":".join(left) + "::" + ":".join(right)
        candidate = head + (str(v4) if head.endswith("::") else ":" + str(v4))
    else:
        candidate = ":".join(disp) + ":" + str(v4)
    try:
        if ipaddress.IPv6Address(candidate) == combined:
            return candidate
    except ValueError:
        pass
    return ":".join(groups) + ":" + str(v4)            # safe fallback


def embed_ipv4_in_prefix(prefix_text, ipv4_text):
    """Place an IPv4 address into the low 32 bits of an IPv6 prefix.

    Cosmetic embedding (no protocol meaning unless the prefix is NAT64/mapped).
    Also returns a random documentation-range (RFC 3849) example.
    """
    pt, at = prefix_text.strip(), ipv4_text.strip()
    if not pt:
        return {"error": "Enter an IPv6 prefix, e.g. fd2b:1a9c:7e3f::/48"}
    if not at:
        return {"error": "Enter an IPv4 address, e.g. 192.168.1.1"}
    try:
        net = ipaddress.ip_network(pt, strict=False)
    except ValueError as e:
        return {"error": f"Invalid IPv6 prefix: {e}"}
    if net.version != 6:
        return {"error": "Prefix must be IPv6, e.g. 2001:db8:abcd::/48"}
    try:
        v4 = ipaddress.IPv4Address(at)
    except ValueError as e:
        return {"error": f"Invalid IPv4 address: {e}"}
    iv = int(v4)
    combined = ipaddress.IPv6Address((int(net.network_address) >> 32 << 32) | iv)

    # Illustrative example in the documentation range 2001:db8::/32 (RFC 3849),
    # with random subnet hextets so users see a realistic-looking address.
    doc_base = int(ipaddress.IPv6Address("2001:db8::"))
    doc_int = doc_base | (random.getrandbits(16) << 80) | (random.getrandbits(16) << 64)
    doc = ipaddress.IPv6Address((doc_int >> 32 << 32) | iv)

    return {
        "ipv4": str(v4),
        "hex_colon": ":".join(format(b, "02x") for b in v4.packed),
        "hex_packed": v4.packed.hex(),
        "prefix": net.compressed,
        "combined_hex": combined.compressed,
        "combined_v4": _ipv6_mixed(combined, v4),
        "doc_hex": doc.compressed,
        "doc_v4": _ipv6_mixed(doc, v4),
    }


# ----------------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------------
class IPv6CalculatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("660x520")
        self.minsize(580, 460)

        # name -> builder method that populates the input frame (alphabetical)
        self._tools = {
            "Embed IPv4 in Prefix": self._tool_embed,
            "IPv4 Calculator": self._tool_ipv4,
            "IPv4 → Hex": self._tool_v4hex,
            "IPv4-in-IPv6 Embeddings": self._tool_v4to6,
            "IPv6 Calculator": self._tool_subnet,
            "Prefix Converter": self._tool_prefix,
            "Random Address Generator": self._tool_random,
        }

        self._build_menu()
        self._build_widgets()
        self.select_tool("IPv6 Calculator")

    # ---- Menus ----
    def _build_menu(self):
        menubar = tk.Menu(self)

        info_menu = tk.Menu(menubar, tearoff=0)
        info_menu.add_command(label="About", command=self.show_about_text)
        info_menu.add_command(label="Python Libraries", command=self.show_libraries_text)
        info_menu.add_command(label="GitHub", command=self.show_github_text)
        info_menu.add_command(label="RFC References", command=self.show_rfc_text)
        info_menu.add_separator()
        info_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="≡", menu=info_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        for name in self._tools:
            tools_menu.add_command(label=name,
                                   command=lambda n=name: self.select_tool(n))
        menubar.add_cascade(label="Tools", menu=tools_menu)

        self.config(menu=menubar)

    # ---- Static layout (title, current-tool label, input frame, output) ----
    def _build_widgets(self):
        ctk.CTkLabel(self, text=APP_TITLE,
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(14, 0))
        self.tool_label = ctk.CTkLabel(self, text="",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       text_color="gray70")
        self.tool_label.pack(pady=(0, 6))

        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.pack(fill="x", padx=20, pady=6)

        self.output = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=13))
        self.output.pack(fill="both", expand=True, padx=20, pady=(8, 16))
        self.output.configure(state="disabled")

    def select_tool(self, name):
        self.tool_label.configure(text=name)
        for w in self.input_frame.winfo_children():
            w.destroy()
        self._set_output("")
        self._tools[name]()

    # ---- Small builder helpers ----
    def _entry_row(self, label, placeholder, on_return):
        row = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        row.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(row, text=label, width=140, anchor="w").pack(side="left", padx=(10, 8))
        entry = ctk.CTkEntry(row, placeholder_text=placeholder)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry.bind("<Return>", lambda _e: on_return())
        self._attach_entry_menu(entry)
        return entry

    @staticmethod
    def _select_all(inner):
        inner.select_range(0, "end")
        inner.icursor("end")
        return "break"

    def _attach_entry_menu(self, ctk_entry):
        """Right-click Cut/Copy/Paste/Select All (and Ctrl+A) on a CTkEntry.

        Cut/Copy/Paste also work via the usual Ctrl+X/C/V on the underlying
        tk entry; this makes them discoverable and adds Select All.
        """
        inner = ctk_entry._entry            # underlying tkinter.Entry
        menu = tk.Menu(inner, tearoff=0)
        menu.add_command(label="Cut", command=lambda: inner.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: inner.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: inner.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: self._select_all(inner))

        def popup(event):
            inner.focus_set()
            menu.tk_popup(event.x_root, event.y_root)

        inner.bind("<Button-3>", popup)
        inner.bind("<Control-a>", lambda _e: self._select_all(inner))
        inner.bind("<Control-A>", lambda _e: self._select_all(inner))

    def _button_row(self, action_label, action):
        row = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(2, 8))
        ctk.CTkButton(row, text=action_label, command=action).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Clear", command=lambda: self._set_output(""),
                      fg_color="gray30", hover_color="gray25").pack(side="left")

    # ---- Tool: IPv6 Calculator ----
    def _tool_subnet(self):
        self.s_entry = self._entry_row("Address / Prefix:", "2001:db8::/32", self._do_subnet)
        self._button_row("Calculate", self._do_subnet)

    def _do_subnet(self):
        r = calculate_ipv6(self.s_entry.get())
        if "error" in r:
            return self._set_output(r["error"])
        big = r["num_addresses"]
        lines = [
            f"Network address : {r['network']}",
            f"Prefix length   : /{r['prefixlen']}",
            f"First address   : {r['first']}",
            f"Last address    : {r['last']}",
            f"Total addresses : {big:,}",
            "",
            f"Compressed      : {r['compressed']}",
            f"Exploded        : {r['exploded']}",
        ]
        if big > MAX_ENUMERATE:
            lines += ["", f"(Guard rail: {big:,} addresses -- too many to list; "
                          "showing first/last only.)"]
        self._set_output("\n".join(lines))

    # ---- Tool: Random Address Generator ----
    def _tool_random(self):
        row = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        row.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(row, text="Type:", width=140, anchor="w").pack(side="left", padx=(10, 8))
        self.r_kind = ctk.CTkOptionMenu(
            row, values=["Host in prefix", "Documentation", "ULA"])
        self.r_kind.pack(side="left", padx=(0, 10))

        self.r_prefix = self._entry_row("Prefix (optional):", "blank = 2000::/4; e.g. 2001:db8::/64",
                                        self._do_random)
        self.r_count = self._entry_row("How many (1-100):", "1", self._do_random)
        self._button_row("Generate", self._do_random)

    def _do_random(self):
        kind = self.r_kind.get()
        raw = self.r_count.get().strip() or "1"
        if not raw.isdigit() or not 1 <= int(raw) <= MAX_RANDOM:
            return self._set_output(f"'How many' must be a number 1-{MAX_RANDOM}.")
        count = int(raw)
        results = []
        for _ in range(count):
            r = random_address(kind, self.r_prefix.get())
            if "error" in r:
                return self._set_output(r["error"])
            results.append(r["address"])
        header = f"Generated {count} random address(es) -- {r['scope']}:\n"
        body = header + "\n".join(f"  {a}" for a in results)
        if kind == "ULA":
            body += ("\n\nNote: ULAs are fc00::/7 (RFC 4193). Only the fd00::/8 half"
                     "\n(L bit = 1, self-assigned) is usable; the fc00::/8 half is"
                     "\nreserved with no defined allocation, so it is not used.")
        self._set_output(body)

    # ---- Tool: Prefix Converter ----
    def _tool_prefix(self):
        row = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        row.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(row, text="Mode:", width=140, anchor="w").pack(side="left", padx=(10, 8))
        self.p_mode = ctk.CTkOptionMenu(
            row, values=["Prefix length → count & mask",
                         "Address form (compressed/exploded)"])
        self.p_mode.pack(side="left", padx=(0, 10))

        self.p_entry = self._entry_row("Value:", "64  or  2001:db8::1", self._do_prefix)
        self._button_row("Convert", self._do_prefix)

    def _do_prefix(self):
        if self.p_mode.get().startswith("Prefix length"):
            r = convert_prefix_length(self.p_entry.get())
            if "error" in r:
                return self._set_output(r["error"])
            subnets = (f"{r['subnets64']:,}" if r["subnets64"] is not None
                       else "n/a (prefix longer than /64)")
            self._set_output("\n".join([
                f"Prefix length   : /{r['prefix']}",
                f"Address count   : {r['count']:,}",
                f"Netmask (hex)   : {r['mask']}",
                f"/64 subnets     : {subnets}",
            ]))
        else:
            r = convert_address_form(self.p_entry.get())
            if "error" in r:
                return self._set_output(r["error"])
            self._set_output("\n".join([
                f"Compressed : {r['compressed']}",
                f"Exploded   : {r['exploded']}",
            ]))

    # ---- Tool: IPv4 -> IPv6 ----
    def _tool_v4to6(self):
        self.v_entry = self._entry_row("IPv4 Address:", "192.168.1.1", self._do_v4to6)
        self._button_row("Convert", self._do_v4to6)

    def _do_v4to6(self):
        r = ipv4_to_ipv6(self.v_entry.get())
        if "error" in r:
            return self._set_output(r["error"])
        self._set_output("\n".join([
            f"IPv4 address: {r['ipv4']}",
            "",
            "Note: IPv4 and IPv6 are separate address spaces -- there is no real",
            "'conversion'. These are special formats that EMBED an IPv4 address",
            "inside IPv6 for specific purposes. (For two hosts to talk, the",
            "modern answer is dual-stack, not an embedding.)",
            "",
            "=== Currently used ===",
            "",
            "NAT64 well-known prefix   (RFC 6052)",
            f"    {r['nat64']}   ( = 64:ff9b::{r['ipv4']} )",
            "    Lets an IPv6-only client reach an IPv4-only server via a NAT64",
            "    gateway. Actively deployed (e.g. mobile carriers, IPv6-only",
            "    networks). This is the embedding that matters today.",
            "",
            "IPv4-mapped   (RFC 4291, sec. 2.5.5.2)",
            f"    {r['mapped']}",
            "    Used INSIDE a single dual-stack host: the sockets API uses it so",
            "    IPv6 code can accept IPv4 connections. Seen in logs; never routed.",
            "",
            "=== Historical / deprecated (do not use) ===",
            "",
            "6to4 prefix   (RFC 3056; obsoleted by RFC 7526)",
            f"    {r['sixto4']}",
            "    Old auto-tunnel of IPv6 over an IPv4-only network. Deprecated.",
            "",
            "IPv4-compatible   (RFC 4291, sec. 2.5.5.1 -- DEPRECATED)",
            f"    {r['compat']}   ( = ::{r['ipv4']} )",
            "    Obsolete transition format. Must not be used; shown to identify it.",
        ]))

    # ---- Tool: IPv4 Calculator ----
    def _tool_ipv4(self):
        self.i_entry = self._entry_row("Address / Prefix:", "192.168.1.0/24", self._do_ipv4)
        self._button_row("Calculate", self._do_ipv4)

    def _do_ipv4(self):
        r = calculate_ipv4(self.i_entry.get())
        if "error" in r:
            return self._set_output(r["error"])
        self._set_output("\n".join([
            f"Network ID      : {r['network']}",
            f"Broadcast       : {r['broadcast']}",
            f"Netmask         : {r['netmask']}",
            f"Wildcard        : {r['wildcard']}",
            f"Prefix length   : /{r['prefixlen']}",
            f"Total addresses : {r['total']:,}",
            f"Usable hosts    : {r['usable']:,}",
            f"Host range      : {r['first_host']} - {r['last_host']}",
        ]))

    # ---- Tool: IPv4 -> Hex ----
    def _tool_v4hex(self):
        self.h_entry = self._entry_row("IPv4 Address:", "192.168.1.1", self._do_v4hex)
        self._button_row("Convert", self._do_v4hex)

    def _do_v4hex(self):
        r = ipv4_to_hex(self.h_entry.get())
        if "error" in r:
            return self._set_output(r["error"])
        self._set_output("\n".join([
            f"IPv4 address : {r['ipv4']}",
            f"Hex (colon)  : {r['colon']}",
            f"Hex (packed) : {r['packed']}",
            f"0x form      : {r['hexint']}",
            f"Decimal      : {r['decimal']:,}",
        ]))

    # ---- Tool: Embed IPv4 in Prefix ----
    def _tool_embed(self):
        self.e_prefix = self._entry_row("IPv6 Prefix:", "fd2b:1a9c:7e3f::/48", self._do_embed)
        self.e_ipv4 = self._entry_row("IPv4 Address:", "172.31.16.1", self._do_embed)
        self._button_row("Embed", self._do_embed)

    def _do_embed(self):
        r = embed_ipv4_in_prefix(self.e_prefix.get(), self.e_ipv4.get())
        if "error" in r:
            return self._set_output(r["error"])
        self._set_output("\n".join([
            f"IPv4 address    : {r['ipv4']}",
            f"IPv4 as hex     : {r['hex_colon']}  ({r['hex_packed']})",
            f"Into prefix     : {r['prefix']}",
            "",
            f"Embedded (hex)  : {r['combined_hex']}",
            f"Embedded (IPv4) : {r['combined_v4']}",
            "",
            "Note: a cosmetic layout -- the embedded bits carry no protocol",
            "meaning unless the prefix is a translation prefix (NAT64 / mapped).",
            "",
            "Example, documentation range (RFC 3849) -- random each click:",
            f"    {r['doc_hex']}",
            f"    {r['doc_v4']}",
        ]))

    # ---- Menu sections (printed into the output box, no pop-up) ----
    def _set_output(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def show_about_text(self):
        self._set_output(
            f"{APP_TITLE}\n"
            f"Version: {VERSION}\n\n"
            "A small toolkit of IPv6/IPv4 utilities. Pick a tool from the "
            "Tools menu.\n\n"
            "Developed and designed by Ron Staples."
        )

    def show_libraries_text(self):
        self._set_output(
            "Python Libraries used:\n\n"
            f"  customtkinter {ctk.__version__}  - GUI (dark mode)\n"
            "  ipaddress (stdlib)     - IPv4/IPv6 math\n"
            "  random (stdlib)        - random address generation\n"
            "  tkinter (stdlib)       - menu bar"
        )

    def show_github_text(self):
        self._set_output(f"GitHub:\n\n  {GITHUB_URL}")

    def show_rfc_text(self):
        self._set_output(
            "RFC References (IPv6):\n\n"
            "  RFC 8200 - Internet Protocol, Version 6 (IPv6) Specification\n"
            "  RFC 4291 - IPv6 Addressing Architecture\n"
            "  RFC 5952 - Recommendation for IPv6 Address Text Representation\n"
            "  RFC 4193 - Unique Local IPv6 Unicast Addresses\n"
            "  RFC 3849 - IPv6 Address Prefix Reserved for Documentation\n"
            "  RFC 6052 - IPv6 Addressing of IPv4/IPv6 Translators (NAT64)\n"
            "  RFC 3056 - Connection of IPv6 Domains via IPv4 Clouds (6to4)\n"
            "  RFC 7526 - Deprecating 6to4 (anycast prefix 192.88.99.0/24)\n"
            "  RFC 4632 - Classless Inter-Domain Routing (CIDR)"
        )


if __name__ == "__main__":
    IPv6CalculatorApp().mainloop()
