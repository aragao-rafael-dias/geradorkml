from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

from flask import Flask, Response, render_template_string, request
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.validation import explain_validity
import simplekml

import os


app = Flask(__name__)

# SIRGAS 2000 / UTM zone 24S -> WGS84
# Se depois vocês confirmarem outro EPSG, basta trocar aqui.
UTM24S_EPSG = "EPSG:31984"
WGS84_EPSG = "EPSG:4326"

transformer_to_wgs84 = Transformer.from_crs(UTM24S_EPSG, WGS84_EPSG, always_xy=True)

HTML = """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Gerador de KML por Vértices</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #f7f7fb;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --border: #d1d5db;
      --danger: #b91c1c;
      --success: #166534;
      --accent: #1d4ed8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .container {
      max-width: 1200px;
      margin: 24px auto;
      padding: 0 16px;
    }
    .title {
      margin-bottom: 16px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 16px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    label {
      display: block;
      font-weight: 600;
      margin: 12px 0 6px;
    }
    input[type="text"], textarea, select {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 14px;
      background: #fff;
    }
    textarea {
      min-height: 280px;
      resize: vertical;
      font-family: Consolas, Monaco, monospace;
      line-height: 1.45;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }
    button {
      border: 0;
      border-radius: 8px;
      padding: 10px 16px;
      font-weight: 700;
      cursor: pointer;
    }
    .primary {
      background: var(--accent);
      color: white;
    }
    .secondary {
      background: #e5e7eb;
      color: #111827;
    }
    .msg {
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 12px;
      font-size: 14px;
    }
    .msg.error {
      background: #fee2e2;
      color: var(--danger);
      border: 1px solid #fecaca;
    }
    .msg.success {
      background: #dcfce7;
      color: var(--success);
      border: 1px solid #bbf7d0;
    }
    .meta {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 12px;
    }
    .meta div {
      background: #f9fafb;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      font-size: 14px;
    }
    .muted {
      color: var(--muted);
      font-size: 13px;
    }
    .preview-box {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px;
      background: white;
      min-height: 480px;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: auto;
    }
    .pill {
      display: inline-block;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      background: #eef2ff;
      color: #3730a3;
      margin-top: 6px;
    }
    .footer-note {
      margin-top: 10px;
      font-size: 12px;
      color: var(--muted);
    }
    @media (max-width: 900px) {
      .grid, .row, .meta {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="title">
      <h1>Gerador de KML por Vértices</h1>
      <div class="muted">SRC fixo: SIRGAS 2000 / UTM 24S</div>
    </div>

    {% if error %}
      <div class="msg error">{{ error }}</div>
    {% endif %}

    {% if success %}
      <div class="msg success">{{ success }}</div>
    {% endif %}

    <div class="grid">
      <div class="card">
        <form method="post" action="/">
          <div class="row">
            <div>
              <label for="protocolo">Protocolo</label>
              <input type="text" id="protocolo" name="protocolo" value="{{ protocolo }}" placeholder="Ex.: 2025-00123" required>
            </div>
            <div>
              <label for="tipo">Tipo</label>
              <select id="tipo" name="tipo">
                <option value="lote" {% if tipo == 'lote' %}selected{% endif %}>Lote</option>
                <option value="edificacao" {% if tipo == 'edificacao' %}selected{% endif %}>Edificação</option>
              </select>
            </div>
          </div>

          <label for="pontos">Pontos</label>
          <textarea id="pontos" name="pontos" placeholder="Ex.:
Ponto 1: 645389.0887626424, 8792436.71632438
Ponto 2: 645392.5047325547, 8792433.707940618
Ponto 3: 645395.2611085888, 8792436.664829656">{{ pontos }}</textarea>

          <div class="footer-note">
            Aceita linhas no formato <strong>X, Y</strong> ou <strong>Ponto N: X, Y</strong>.
          </div>

          <div class="actions">
            <button class="primary" type="submit" name="action" value="preview">Validar e visualizar</button>
            <button class="secondary" type="submit" name="action" value="invert">Inverter ordem dos pontos</button>
          </div>
        </form>

        {% if polygon_info %}
          <div class="meta">
            <div><strong>Vértices:</strong><br>{{ polygon_info.vertex_count }}</div>
            <div><strong>Fechado automaticamente:</strong><br>{{ "Sim" if polygon_info.closed_automatically else "Não" }}</div>
            <div><strong>Área:</strong><br>{{ polygon_info.area_m2 }} m²</div>
            <div><strong>Perímetro:</strong><br>{{ polygon_info.perimeter_m }} m</div>
            <div><strong>Válido:</strong><br>{{ "Sim" if polygon_info.is_valid else "Não" }}</div>
            <div><strong>Detalhe:</strong><br>{{ polygon_info.validity_message }}</div>
          </div>

          <div class="pill">UTM 24S → WGS84 na exportação KML</div>

          {% if polygon_info.is_valid %}
            <form method="post" action="/download-kml">
              <input type="hidden" name="protocolo" value="{{ protocolo }}">
              <input type="hidden" name="tipo" value="{{ tipo }}">
              <input type="hidden" name="pontos" value="{{ pontos }}">
              <div class="actions">
                <button class="primary" type="submit">Gerar KML</button>
              </div>
            </form>
          {% endif %}
        {% endif %}
      </div>

      <div class="card">
        <h3 style="margin-top: 0;">Visualizador 2D</h3>
        <div class="muted">Prévia leve do polígono, sem ortofoto.</div>
        <div class="preview-box">
          {% if preview_svg %}
            {{ preview_svg|safe }}
          {% else %}
            <div class="muted">A prévia aparecerá aqui após validar os pontos.</div>
          {% endif %}
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""


@dataclass
class PolygonInfo:
    vertex_count: int
    closed_automatically: bool
    area_m2: str
    perimeter_m: str
    is_valid: bool
    validity_message: str


def parse_points(raw_text: str) -> List[Tuple[float, float]]:
    """
    Aceita:
    - '645389.08, 8792436.71'
    - 'Ponto 1: 645389.08, 8792436.71'
    - espaços extras
    """
    points: List[Tuple[float, float]] = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", line)
        if len(numbers) < 2:
            continue

        x = float(numbers[-2])
        y = float(numbers[-1])
        points.append((x, y))

    return points


def points_to_text(points: List[Tuple[float, float]]) -> str:
    lines = []
    for idx, (x, y) in enumerate(points, start=1):
        lines.append(f"Ponto {idx}: {x}, {y}")
    return "\n".join(lines)


def ensure_closed(points: List[Tuple[float, float]]) -> Tuple[List[Tuple[float, float]], bool]:
    if not points:
        return points, False
    if points[0] == points[-1]:
        return points, False
    return points + [points[0]], True


def build_polygon(points: List[Tuple[float, float]]) -> Tuple[Polygon, bool]:
    closed_points, closed_automatically = ensure_closed(points)
    polygon = Polygon(closed_points)
    return polygon, closed_automatically


def format_number(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def make_polygon_info(polygon: Polygon, original_points: List[Tuple[float, float]], closed_automatically: bool) -> PolygonInfo:
    is_valid = polygon.is_valid
    validity_message = "Geometria válida" if is_valid else explain_validity(polygon)

    return PolygonInfo(
        vertex_count=len(original_points),
        closed_automatically=closed_automatically,
        area_m2=format_number(polygon.area),
        perimeter_m=format_number(polygon.length),
        is_valid=is_valid,
        validity_message=validity_message,
    )


def polygon_to_svg(points: List[Tuple[float, float]], width: int = 520, height: int = 520) -> str:
    if len(points) < 3:
        return '<div class="muted">Pontos insuficientes para desenhar um polígono.</div>'

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    dx = max(max_x - min_x, 1.0)
    dy = max(max_y - min_y, 1.0)

    padding = 40
    scale_x = (width - 2 * padding) / dx
    scale_y = (height - 2 * padding) / dy
    scale = min(scale_x, scale_y)

    def project(pt: Tuple[float, float]) -> Tuple[float, float]:
        x, y = pt
        px = padding + (x - min_x) * scale
        py = height - padding - (y - min_y) * scale
        return px, py

    svg_points = [project(p) for p in points]
    if svg_points[0] != svg_points[-1]:
        svg_points.append(svg_points[0])

    polyline_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in svg_points)

    vertex_circles = []
    labels = []

    for idx, (x, y) in enumerate(svg_points[:-1], start=1):
        vertex_circles.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#dc2626" stroke="#ffffff" stroke-width="2" />'
        )
        labels.append(
            f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" font-size="14" fill="#111827" font-weight="700">{idx}</text>'
        )

    bbox = (
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" '
        f'fill="white" stroke="#d1d5db" stroke-width="1" rx="10" />'
    )

    grid_lines = []
    for i in range(1, 5):
        gx = padding + i * (width - 2 * padding) / 5
        gy = padding + i * (height - 2 * padding) / 5
        grid_lines.append(f'<line x1="{gx:.2f}" y1="{padding}" x2="{gx:.2f}" y2="{height-padding}" stroke="#eef2f7" stroke-width="1"/>')
        grid_lines.append(f'<line x1="{padding}" y1="{gy:.2f}" x2="{width-padding}" y2="{gy:.2f}" stroke="#eef2f7" stroke-width="1"/>')

    svg = f"""
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Prévia do polígono">
      {bbox}
      {''.join(grid_lines)}
      <polygon points="{polyline_str}" fill="#93c5fd88" stroke="#1d4ed8" stroke-width="3" />
      {''.join(vertex_circles)}
      {''.join(labels)}
    </svg>
    """
    return svg


def to_kml_coords(points_utm: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    coords_wgs84 = []
    for x, y in points_utm:
        lon, lat = transformer_to_wgs84.transform(x, y)
        coords_wgs84.append((lon, lat))
    return coords_wgs84


def generate_kml_bytes(protocolo: str, tipo: str, points_utm: List[Tuple[float, float]]) -> bytes:
    polygon, _ = build_polygon(points_utm)
    if not polygon.is_valid:
        raise ValueError(f"Geometria inválida: {explain_validity(polygon)}")

    closed_points, _ = ensure_closed(points_utm)
    coords_wgs84 = to_kml_coords(closed_points)

    kml = simplekml.Kml()
    name = f"{protocolo}_{tipo}"
    pol = kml.newpolygon(name=name)

    pol.outerboundaryis = coords_wgs84
    pol.description = (
        f"Protocolo: {protocolo}\n"
        f"Tipo: {tipo}\n"
        f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Vertices: {len(points_utm)}\n"
        f"SRC de entrada: SIRGAS 2000 / UTM 24S\n"
        f"SRC de saída: WGS84 (KML)"
    )

    pol.style.linestyle.width = 3
    pol.style.linestyle.color = simplekml.Color.red
    pol.style.polystyle.color = simplekml.Color.changealphaint(80, simplekml.Color.red)

    return kml.kml().encode("utf-8")


def validate_input(protocolo: str, tipo: str, raw_points: str) -> Tuple[List[Tuple[float, float]], str | None]:
    protocolo = protocolo.strip()
    tipo = tipo.strip()

    if not protocolo:
        return [], "Informe o protocolo."

    if tipo not in {"lote", "edificacao"}:
        return [], "Tipo inválido."

    points = parse_points(raw_points)
    if len(points) < 3:
        return [], "Informe pelo menos 3 pontos válidos."

    unique_points = set(points)
    if len(unique_points) < 3:
        return [], "Há poucos pontos distintos para formar um polígono."

    return points, None


@app.route("/", methods=["GET", "POST"])
def index():
    protocolo = ""
    tipo = "lote"
    pontos = ""
    error = None
    success = None
    polygon_info = None
    preview_svg = None

    if request.method == "POST":
        protocolo = request.form.get("protocolo", "")
        tipo = request.form.get("tipo", "lote")
        pontos = request.form.get("pontos", "")
        action = request.form.get("action", "preview")

        points, error = validate_input(protocolo, tipo, pontos)

        if not error:
            if action == "invert":
                points = list(reversed(points))
                pontos = points_to_text(points)
                success = "Ordem dos pontos invertida."

            polygon, closed_automatically = build_polygon(points)
            polygon_info = make_polygon_info(polygon, points, closed_automatically)
            preview_svg = polygon_to_svg(points)

    return render_template_string(
        HTML,
        protocolo=protocolo,
        tipo=tipo,
        pontos=pontos,
        error=error,
        success=success,
        polygon_info=polygon_info,
        preview_svg=preview_svg,
    )


@app.route("/download-kml", methods=["POST"])
def download_kml():
    protocolo = request.form.get("protocolo", "")
    tipo = request.form.get("tipo", "lote")
    pontos = request.form.get("pontos", "")

    points, error = validate_input(protocolo, tipo, pontos)
    if error:
        return Response(error, status=400, mimetype="text/plain; charset=utf-8")

    polygon, _ = build_polygon(points)
    if not polygon.is_valid:
        return Response(
            f"Geometria inválida: {explain_validity(polygon)}",
            status=400,
            mimetype="text/plain; charset=utf-8",
        )

    kml_bytes = generate_kml_bytes(protocolo, tipo, points)
    filename = f"{sanitize_filename(protocolo)}_{tipo}.kml"

    return Response(
        kml_bytes,
        mimetype="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def sanitize_filename(value: str) -> str:
    value = value.strip().replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_\\-\\.]", "", value)
    return value or "arquivo"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)