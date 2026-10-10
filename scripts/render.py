#!/usr/bin/env python3
"""render.py — one cross-platform entry point for deck -> per-page PNG.

This exists to handle one trap, and it is the only trap that matters here:

    rendering a .pptx straight to PNG in this environment draws the slide
    content at 1.5x and crops the bottom-right of every page. Going through
    PDF is correct.

  python render.py --deck deck.pptx --out preview [--dpi 110] [--pages 1,3]
  python render.py --describe              # what renderers were found
  python render.py --calibrate             # prove the route is 1:1, not 1.5x
  python render.py --register <cli.js> [--node <node.exe>]

Route order: explicit/env kit -> registered kit -> autodiscovered kit ->
soffice + PyMuPDF -> soffice + pdftoppm. Everything goes via PDF.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import hashlib
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
from state_paths import state_path, read_json, write_json
REGISTRY = str(state_path("render.json"))
from canvas import DECK_CANVAS
PAGE_W, PAGE_H = DECK_CANVAS.width, DECK_CANVAS.height


def load_registry():
    return read_json('render.json',{})


def save_registry(d):
    return write_json('render.json',d)


def run(cmd, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(str(c) for c in cmd[:3])}... failed "
                           f"({p.returncode}): {(p.stderr or p.stdout)[:500]}")
    return p


def workspace(prefix, parent=None):
    """On Windows inherit the selected parent's ACL for new work/output files.

    CPython's 0700 mkdtemp creates an owner-only ACL on Windows. Moving files
    from that directory preserves it, preventing subsequent artifact readers.
    No existing ACL or execution permissions are changed here.
    """
    if os.name != 'nt':
        return tempfile.mkdtemp(prefix=prefix, dir=parent)
    from pathlib import Path
    path = Path(parent or tempfile.gettempdir()) / (prefix + uuid.uuid4().hex)
    path.mkdir(mode=0o777)
    return str(path)


def find_node():
    for cand in (os.environ.get("RISOSLIDES_NODE"), shutil.which("node")):
        if cand and os.path.exists(cand):
            return cand
    return None


def find_kit(args):
    """Return (node, cli) for a libreoffice-kit style CLI, or (None, None)."""
    reg = load_registry()
    for cli in (args.kit, os.environ.get("RISOSLIDES_KIT"), reg.get("kit")):
        if cli and os.path.exists(cli):
            node = args.node or reg.get("node") or find_node()
            if node:
                return node, cli
    if not args.autodiscover:
        return None, None
    roots = [os.environ.get("DSH_HOME"), os.path.dirname(HERE),
             os.path.abspath(os.path.join(HERE, "..", "..")),
             os.path.expanduser("~/AppData/Local")]
    pat = os.path.join("*", "node_modules", "@deepseek-ai", "libreoffice-kit",
                       "lib", "cli.js")
    seen = set()
    for root in roots:
        if not root or not os.path.isdir(root) or root in seen:
            continue
        seen.add(root)
        for depth in ("", "*", "*/*", "*/*/*"):
            for hit in glob.glob(os.path.join(root, depth, pat)):
                node = find_node()
                if node:
                    return node, hit
    return None, None


def find_soffice():
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
              "/Applications/LibreOffice.app/Contents/MacOS/soffice",
              "/usr/bin/soffice", "/usr/bin/libreoffice"):
        if os.path.exists(p):
            return p
    return None


def describe(args):
    node, cli = find_kit(args)
    soffice = find_soffice()
    try:
        import fitz  # noqa: F401
        has_fitz = True
    except Exception:
        has_fitz = False
    pop = shutil.which("pdftoppm")
    print("renderers:")
    print(f"  libreoffice-kit : {'yes' if cli else 'not found in configured locations' if args.autodiscover else 'autodiscovery NOT SEARCHED'}"
          + (f"  node={node}\n                    cli={cli}" if cli else ""))
    print(f"  system soffice  : {soffice or 'no'}")
    print(f"  PyMuPDF (fitz)  : {'yes' if has_fitz else 'no'}")
    print(f"  pdftoppm        : {pop or 'no'}")
    route = pick_route(args)
    print(f"  chosen route    : {route or 'NONE'}")
    print(f"  discovery       : {discovery_message(args, route)}")
    if route:
        print('  execution       : UNVERIFIED by --describe; run a real conversion probe')
    return 0 if route else 1


def discovery_message(args, route):
    """Discovery is distinct from both execution and an unrequested search."""
    if route:
        return 'renderer found (discovery only)'
    if not args.autodiscover:
        return ('no renderer searched in install roots: kit autodiscovery was NOT executed; '
                'configured kit/system routes did not resolve. Try --autodiscover or --kit '
                '<cli.js> --node <node.exe> (or register a kit).')
    return ('no renderer found after --autodiscover and configured/system route checks; '
            'provide --kit <cli.js> --node <node.exe> or install a renderer')


def pick_route(args):
    node, cli = find_kit(args)
    if cli:
        return ("kit", node, cli)
    soffice = find_soffice()
    if soffice:
        try:
            import fitz  # noqa: F401
            return ("soffice+fitz", soffice, None)
        except Exception:
            pass
        pop = shutil.which("pdftoppm")
        if pop:
            return ("soffice+pdftoppm", soffice, pop)
    return None


def to_pdf(route, deck, outdir):
    kind = route[0]
    os.makedirs(outdir, exist_ok=True)
    if kind == "kit":
        node, cli = route[1], route[2]
        pdf = os.path.join(outdir, os.path.splitext(os.path.basename(deck))[0] + ".pdf")
        if os.path.exists(pdf):
            os.remove(pdf)
        p = run([node, cli, "convert", "--input", deck, "--output", pdf])
        info = {}
        try:
            info = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            pass
        return pdf, info
    soffice = route[1]
    run([soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, deck])
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(deck))[0] + ".pdf")
    if not os.path.exists(pdf):
        raise RuntimeError("soffice did not produce a PDF")
    return pdf, {}


def render_pdf(route, pdf, outdir, dpi, pages=None):
    kind = route[0]
    if kind != "kit":
        os.makedirs(outdir, exist_ok=True)
    if kind == "kit":
        # the kit refuses to write into a directory that already exists, so let
        # it create the output dir itself
        node, cli = route[1], route[2]
        cmd = [node, cli, "render", "--input", pdf, "--output-dir", outdir,
               "--dpi", str(dpi)]
        if pages:
            cmd += ["--pages", pages]
        p = run(cmd)
        try:
            return json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            return {}
    if kind == "soffice+fitz":
        import fitz
        doc = fitz.open(pdf)
        want = [int(x) for x in pages.split(",")] if pages else range(1, len(doc) + 1)
        for i in want:
            doc[i - 1].get_pixmap(dpi=dpi).save(os.path.join(outdir, f"page-{i:04d}.png"))
        return {"pageCount": len(doc), "missingFonts": []}
    if kind == "soffice+pdftoppm":
        pop = route[2]
        cmd = [pop, "-png", "-r", str(dpi), pdf, os.path.join(outdir, "page")]
        run(cmd)
        return {"pageCount": len(glob.glob(os.path.join(outdir, "page-*.png")))}
    raise RuntimeError("no rasteriser")


def check_scale(png):
    """Read raster dimensions for comparison with the actual PPTX canvas."""
    try:
        from PIL import Image
    except Exception:
        return None
    with Image.open(png) as img:
        return img.size


def calibrate(args):
    """Build a probe deck with a known rectangle and verify 1:1 output."""
    sys.path.insert(0, HERE)
    import riso_kit as rk
    from pptx.util import Pt
    tmp = tempfile.mkdtemp(prefix="riso_cal_")
    prs = rk.new_deck()
    s = rk.add_page(prs, None)
    rk.rect(s, 100, 100, 200, 100, fill="D7261E")
    probe = os.path.join(tmp, "probe.pptx")
    prs.save(probe)
    route = pick_route(args)
    if not route:
        print("no renderer available")
        return 1
    print(f"route: {route[0]}")
    pdf, _ = to_pdf(route, probe, os.path.join(tmp, "pdf"))
    out = os.path.join(tmp, "png")
    render_pdf(route, pdf, out, args.dpi)
    png = sorted(glob.glob(os.path.join(out, "page-*.png")))
    if not png:
        print("no image produced")
        return 1
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(png[0]).convert("RGB")).astype(int)
    m = (np.abs(a - np.array([215, 38, 30])).sum(axis=2) < 40)
    if not m.any():
        print("probe rectangle not found in the render")
        return 1
    w = a.shape[1]
    px_pt = w / float(PAGE_W)
    ys, xs = np.where(m)
    got = (xs.min() / px_pt, ys.min() / px_pt, xs.max() / px_pt, ys.max() / px_pt)
    want = (100, 100, 300, 200)
    scale = (got[2] - got[0]) / (want[2] - want[0])
    ok = abs(scale - 1.0) < 0.02
    print(f"expected rect {want} pt, measured "
          f"({got[0]:.0f}, {got[1]:.0f}, {got[2]:.0f}, {got[3]:.0f}) pt")
    print(f"scale factor {scale:.3f}")
    if ok:
        print("OK — this route renders slides 1:1.")
    else:
        print("WARNING — content is scaled; renders will be cropped. "
              "Use a PDF-based route (this script's default).")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="riso-slides renderer")
    ap.add_argument("--deck")
    ap.add_argument("--out", default=None, help="preview directory")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--pages", default=None, help='e.g. "1,3,5"')
    ap.add_argument("--kit", default=None, help="path to a libreoffice-kit cli.js")
    ap.add_argument("--node", default=None)
    ap.add_argument("--autodiscover", action="store_true",
                    help="search common install roots for a kit")
    ap.add_argument("--keep-pdf", action="store_true")
    ap.add_argument("--work-dir", help="writable parent for isolated conversion workspace")
    ap.add_argument("--describe", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--register", metavar="CLI_JS",
                    help="remember a kit location for future runs")
    args = ap.parse_args()

    if args.register:
        if not os.path.exists(args.register):
            print(f"not found: {args.register}")
            return 2
        node = args.node or find_node()
        save_registry({"kit": os.path.abspath(args.register), "node": node})
        print(f"registered kit: {args.register}\nnode: {node}\n-> {REGISTRY}")
        return 0
    if args.describe:
        return describe(args)
    if args.calibrate:
        return calibrate(args)
    if args.dpi <= 0:
        ap.error('--dpi must be positive')
    if not args.deck:
        ap.error("--deck is required (or use --describe / --calibrate / --register)")

    out = args.out or os.path.splitext(args.deck)[0] + "-preview"
    route = pick_route(args)
    if not route:
        print("error: " + discovery_message(args, route) + "\n"
              "  * register a bundled LibreOffice kit:  "
              "render.py --register <...>/libreoffice-kit/lib/cli.js\n"
              "  * or install LibreOffice (soffice) plus PyMuPDF or poppler",
              file=sys.stderr)
        return 3
    print(f"route: {route[0]}")

    work=None
    try:
        parent=None
        if args.work_dir:
            from pathlib import Path
            parent=Path(args.work_dir).expanduser().resolve()
            parent.mkdir(parents=True,exist_ok=True)
            if not parent.is_dir():raise OSError(f'Not a directory: {parent}')
        work=workspace('riso_render_',parent)
        probe=os.path.join(work,'write-probe')
        with open(probe,'wb') as fh:fh.write(b'probe')
        os.remove(probe)
        source=os.path.abspath(args.deck)
        out=os.path.abspath(out)
        same_drive=os.path.splitdrive(source)[0].casefold()==os.path.splitdrive(out)[0].casefold()
        if same_drive and os.path.commonpath([source,out])==out:
            raise ValueError('Preview directory must not contain the source PPTX')
        if not os.path.isfile(source):raise OSError(f'Missing PPTX: {source}')
        pdf, conv = to_pdf(route, args.deck, os.path.join(work, "pdf"))
        stage = os.path.join(work, "png")
        info = render_pdf(route, pdf, stage, args.dpi, args.pages)
        from pathlib import Path
        pngs=sorted(Path(stage).glob('page-*.png'))
        if not pngs:raise RuntimeError('Renderer produced no page PNGs')
        if not os.path.isfile(pdf):
            raise RuntimeError('Renderer produced an invalid PDF')
        with open(pdf,'rb') as header:
            if header.read(5)!=b'%PDF-':raise RuntimeError('Renderer produced an invalid PDF')
        from PIL import Image
        for png in pngs:
            with Image.open(png) as img:img.verify()
        metadata=Path(work)/'render.json'
        metadata.write_text(json.dumps({'source_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                                       'route':route[0],'dpi':args.dpi,
                                       'pages':[p.name for p in pngs]},indent=2),encoding='utf-8')
        # Publish only complete, verified outputs. Never delete a user-selected
        # directory recursively, and never leave partial conversion files there.
        Path(out).mkdir(parents=True,exist_ok=True)
        publish=workspace('.riso-publish-',out)
        try:
            files=list(pngs)+([Path(pdf)] if args.keep_pdf else [])+[metadata]
            for item in files:shutil.copy2(item,Path(publish)/item.name)
            for item in files:os.replace(Path(publish)/item.name,Path(out)/item.name)
            current={png.name for png in pngs}
            for stale in Path(out).glob('page-*.png'):
                if stale.name not in current:stale.unlink()
        finally:
            shutil.rmtree(publish,ignore_errors=True)
        missing = info.get("missingFonts") or conv.get("missingFonts") or []
        n = len(glob.glob(os.path.join(out, "page-*.png")))
        print(f"preview -> {out} ({n} pages at {args.dpi} dpi)")
        if missing:
            print(f"warning: missing fonts reported by the renderer: {missing}")
        first = sorted(glob.glob(os.path.join(out, "page-*.png")))
        if first:
            size = check_scale(first[0])
            from pptx import Presentation
            prs = Presentation(args.deck)
            expect_w = int(round(prs.slide_width.pt / 72.0 * args.dpi))
            expect_h = int(round(prs.slide_height.pt / 72.0 * args.dpi))
            if size and (abs(size[0] - expect_w) > 2 or abs(size[1] - expect_h) > 2):
                print(f"warning: page image is {size[0]}x{size[1]}px, expected "
                      f"{expect_w}x{expect_h}px — the renderer may be scaling content "
                      f"(run --calibrate)")
        return 0
    except (OSError,RuntimeError,ValueError) as exc:
        print(f'error: renderer execution/workdir failure ({args.work_dir or "system temp"}): {exc}',file=sys.stderr)
        return 4
    finally:
        if work:shutil.rmtree(work,ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
