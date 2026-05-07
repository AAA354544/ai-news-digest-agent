from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.generators.report_generator import (
    load_latest_digest,
    render_html_report,
    render_markdown_report,
    save_report_files,
)


def main() -> None:
    try:
        digest = load_latest_digest(input_dir=str(PROJECT_ROOT / "data" / "digested"))
    except FileNotFoundError as exc:
        print(str(exc))
        return

    markdown_text = render_markdown_report(digest, template_dir=str(PROJECT_ROOT / "templates"))
    html_text = render_html_report(digest, template_dir=str(PROJECT_ROOT / "templates"))
    md_path, html_path = save_report_files(
        digest,
        markdown_text,
        html_text,
        output_base_dir=str(PROJECT_ROOT / "outputs"),
    )

    selected_count = sum(len(group.items) for group in digest.main_digest)
    print(f"digest date: {digest.date}")
    print(f"topic: {digest.topic}")
    print(f"category count: {len(digest.main_digest)}")
    print(f"selected item count: {selected_count}")
    print(f"appendix count: {len(digest.appendix)}")
    print(f"markdown path: {md_path}")
    print(f"html path: {html_path}")
    print("markdown preview (first 500 chars):")
    print(markdown_text[:500])
    print("Module 5 report generation test completed.")


if __name__ == "__main__":
    main()
