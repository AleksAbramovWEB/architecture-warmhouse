#!/usr/bin/env python3
"""Render all As-Is and To-Be PlantUML diagrams using one local JAR."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def find_jar():
    configured = os.environ.get("PLANTUML_JAR")
    if configured:
        jar = Path(configured).expanduser()
        if not jar.is_file():
            raise ValueError(f"PLANTUML_JAR указывает на отсутствующий файл: {jar}")
        return jar.resolve()

    plugins = Path.home() / "Library/Application Support/JetBrains"
    candidates = sorted(
        plugins.glob("*/plugins/intellij-omni-viewer/lib/plantuml-*.jar"),
        reverse=True,
    )
    if not candidates:
        raise ValueError(
            "JAR PlantUML не найден. Задайте PLANTUML_JAR фактическим путём "
            "к установленному JAR со стандартной библиотекой C4."
        )
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png-dir", type=Path, help="Также создать PNG для визуальной проверки")
    args = parser.parse_args()
    jar = find_jar()
    sources = sorted(
        path for path in (ROOT / "docs/diagrams").rglob("*.puml")
        if not path.name.startswith("_")
    )
    if not sources:
        raise ValueError("В docs/diagrams нет исходников PlantUML.")

    command = [
        os.environ.get("JAVA_BIN", "java"),
        "-Djava.awt.headless=true", "-jar", str(jar),
        "-charset", "UTF-8", "-stdrpt:1",
    ]
    print(f"PlantUML: {jar}", flush=True)
    for folder, label in (("as-is", "As-Is"), ("to-be", "To-Be")):
        count = sum((ROOT / "docs/diagrams" / folder) in path.parents for path in sources)
        print(f"Диаграммы {label}: {count}", flush=True)
    subprocess.run(command + ["-tsvg", *map(str, sources)], check=True, cwd=ROOT)
    for source in sources:
        svg = source.with_suffix(".svg")
        labels = " ".join(ET.parse(svg).getroot().itertext())
        if "Syntax Error" in labels:
            raise ValueError(f"Ошибка PlantUML в {source}")

    if args.png_dir:
        output = args.png_dir.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            command + ["-tpng", "-o", str(output), *map(str, sources)],
            check=True, cwd=ROOT,
        )
    print(f"Успешно: {len(sources)} диаграмм, SVG проверены.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"Не удалось сгенерировать диаграммы: {error}", file=sys.stderr)
        sys.exit(1)
