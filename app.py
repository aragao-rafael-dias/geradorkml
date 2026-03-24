from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

from flask import Flask, Response, render_template_string, request
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.validation import explain_validity
import simplekml


app = Flask(__name__)

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
      max-width: 1280px;
      margin: 24px auto;
      padding: 0 16px;
    }

    .title {
      margin-bottom: 16px;
    }

    .grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
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
      min-height: 320px;
      resize: vertical;
      font-family: Consolas, Monaco, monospace;
      line-height: 1.45;
    }

    .desc-textarea {
      min-height: 90px;
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.4;
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
      margin-right: 6px;
    }

    .footer-note {
      margin-top: 10px;
      font-size: 12px;
      color: var(--muted);
    }

    .lot-box {
      margin-top: 16px;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #f8fafc;
    }

    .lot-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
      margin-top: 10px;
    }

    .poly-card {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: #fff;
      padding: 0;
      overflow: hidden;
    }

    .poly-card summary {
      cursor: pointer;
      list-style: none;
      padding: 14px 16px;
      background: #f8fafc;
      border-bottom: 1px solid var(--border);
      font-weight: 700;
    }

    .poly-card[open] summary {
      background: #eef2ff;
    }

    .poly-card summary::-webkit-details-marker {
      display: none;
    }

    .poly-card > div {
      padding: 14px;
    }

    .details-box {
      margin-top: 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #fafafa;
      padding: 8px 10px;
    }

    details summary {
      user-select: none;
    }

    .summary-note {
      margin-top: 4px;
      font-size: 12px;
      color: var(--muted);
    }

    @media (max-width: 900px) {
      .grid, .row, .meta, .lot-grid {
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
              <label for="inscricao">Inscrição</label>
              <input type="text" id="inscricao" name="inscricao" value="{{ inscricao }}" placeholder="Ex.: 2025-00123" required>
            </div>
            <div>
              <label for="operador">Operador</label>
              <input type="text" id="operador" name="operador" value="{{ operador }}" placeholder="Ex.: Rafael Aragão">
            </div>
          </div>

          <div class="row">
            <div>
              <label for="tipo">Tipo</label>
              <select id="tipo" name="tipo">
                <option value="lote" {% if tipo == 'lote' %}selected{% endif %}>Lote</option>
                <option value="edificacao" {% if tipo == 'edificacao' %}selected{% endif %}>Edificação</option>
              </select>
            </div>
            <div></div>
          </div>

          <label for="pontos">Pontos</label>
          <textarea id="pontos" name="pontos" placeholder="Ex.:
Ponto 1: 645389.0887626424, 8792436.71632438
Ponto 2: 645392.5047325547, 8792433.707940618
Ponto 3: 645395.2611085888, 8792436.664829656

Ponto 1: 645400.0887626424, 8792440.71632438
Ponto 2: 645403.5047325547, 8792438.707940618
Ponto 3: 645406.2611085888, 8792441.664829656">{{ pontos }}</textarea>

          <div class="footer-note">
            Aceita múltiplos polígonos. Um novo polígono começa quando aparece outro <strong>Ponto 1:</strong>
          </div>

          {% if polygon_info_list %}
            <div class="lot-box">
              <strong>Identificação dos polígonos</strong>
              <div class="muted">Informe nome do polígono e, se quiser, uma descrição para cada polígono detectado.</div>

              <div class="lot-grid">
                {% for polygon_info in polygon_info_list %}
                  <details class="poly-card" {% if loop.first %}open{% endif %}>
                    <summary>
                      <strong>{{ lotes_map.get(polygon_info.index, "Polígono " ~ polygon_info.index) }}</strong>
                      <span class="muted"> — Área: {{ polygon_info.area_m2 }} m²</span>
                    </summary>

                    <div>
                      <div class="row">
                        <div>
                          <label for="lote_{{ polygon_info.index }}">Nome do polígono</label>
                          <input
                            type="text"
                            id="lote_{{ polygon_info.index }}"
                            name="lote_{{ polygon_info.index }}"
                            value="{{ lotes_map.get(polygon_info.index, '') }}"
                            placeholder="Ex.: Lote 59"
                          >
                        </div>
                        <div>
                          <label>Área</label>
                          <input type="text" value="{{ polygon_info.area_m2 }} m²" readonly>
                        </div>
                      </div>

                      <label for="descricao_{{ polygon_info.index }}">Descrição</label>
                      <textarea
                        id="descricao_{{ polygon_info.index }}"
                        name="descricao_{{ polygon_info.index }}"
                        class="desc-textarea"
                        placeholder="Descrição opcional do polígono..."
                      >{{ descricoes_map.get(polygon_info.index, '') }}</textarea>

                      <div class="details-box">
                        <details>
                          <summary>Ver metadados técnicos</summary>
                          <div class="summary-note">Esses dados continuam disponíveis e também seguem nos metadados.</div>
                          <div class="meta">
                            <div><strong>Vértices:</strong><br>{{ polygon_info.vertex_count }}</div>
                            <div><strong>Fechado automaticamente:</strong><br>{{ "Sim" if polygon_info.closed_automatically else "Não" }}</div>
                            <div><strong>Perímetro:</strong><br>{{ polygon_info.perimeter_m }} m</div>
                            <div><strong>Válido:</strong><br>{{ "Sim" if polygon_info.is_valid else "Não" }}</div>
                            <div style="grid-column: 1 / -1;"><strong>Detalhe técnico:</strong><br>{{ polygon_info.validity_message }}</div>
                          </div>
                        </details>
                      </div>
                    </div>
                  </details>
                {% endfor %}
              </div>
            </div>
          {% endif %}

          <div class="actions">
            <button class="primary" type="submit" name="action" value="preview">Validar e visualizar</button>
            <button class="secondary" type="submit" name="action" value="invert">Inverter ordem dos pontos</button>
          </div>
        </form>

        {% if polygon_info_list %}
          <div class="pill">{{ polygon_info_list|length }} polígono(s) detectado(s)</div>
          <div class="pill">UTM 24S → WGS84 na exportação KML</div>

          {% set all_valid = polygon_info_list | selectattr('is_valid') | list | length == polygon_info_list | length %}
          {% if all_valid %}
            <form method="post" action="/download-kml">
              <input type="hidden" name="inscricao" value="{{ inscricao }}">
              <input type="hidden" name="operador" value="{{ operador }}">
              <input type="hidden" name="tipo" value="{{ tipo }}">
              <input type="hidden" name="pontos" value="{{ pontos }}">

              {% for polygon_info in polygon_info_list %}
                <input type="hidden" name="lote_{{ polygon_info.index }}" value="{{ lotes_map.get(polygon_info.index, '') }}">
                <input type="hidden" name="descricao_{{ polygon_info.index }}" value="{{ descricoes_map.get(polygon_info.index, '') }}">
              {% endfor %}

              <div class="actions">
                <button class="primary" type="submit">Gerar KML</button>
              </div>
            </form>
          {% endif %}
        {% endif %}
      </div>

      <div class="card">
        <h3 style="margin-top: 0;">Visualizador 2D</h3>
        <div class="muted">Prévia leve dos polígonos, sem ortofoto.</div>
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
    index: int
    vertex_count: int
    closed_automatically: bool
    area_m2: str
    perimeter_m: str
    is_valid: bool
    validity_message: str


def parse_multiple_polygons(raw_text: str) -> List[List[Tuple[float, float]]]:
    polygons: List[List[Tuple[float, float]]] = []
    current_polygon: List[Tuple[float, float]] = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        ponto_match = re.match(r"(?i)^ponto\s+(\d+)\s*:\s*(.*)$", line)
        if ponto_match:
            point_number = int(ponto_match.group(1))
            remainder = ponto_match.group(2)

            numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", remainder)
            if len(numbers) < 2:
                continue

            x = float(numbers[-2])
            y = float(numbers[-1])

            if point_number == 1 and current_polygon:
                polygons.append(current_polygon)
                current_polygon = []

            current_polygon.append((x, y))
            continue

        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", line)
        if len(numbers) >= 2:
            x = float(numbers[-2])
            y = float(numbers[-1])
            current_polygon.append((x, y))

    if current_polygon:
        polygons.append(current_polygon)

    return polygons


def multiple_polygons_to_text(polygons: List[List[Tuple[float, float]]]) -> str:
    blocks = []

    for polygon in polygons:
        lines = []
        for idx, (x, y) in enumerate(polygon, start=1):
            lines.append(f"Ponto {idx}: {x}, {y}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def extract_lotes_from_form(form, polygon_count: int) -> dict[int, str]:
    lotes_map: dict[int, str] = {}

    for idx in range(1, polygon_count + 1):
        value = form.get(f"lote_{idx}", "").strip()
        if value:
            lotes_map[idx] = value

    return lotes_map


def extract_descricoes_from_form(form, polygon_count: int) -> dict[int, str]:
    descricoes_map: dict[int, str] = {}

    for idx in range(1, polygon_count + 1):
        value = form.get(f"descricao_{idx}", "").strip()
        if value:
            descricoes_map[idx] = value

    return descricoes_map


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


def make_polygon_info(index: int, polygon: Polygon, original_points: List[Tuple[float, float]], closed_automatically: bool) -> PolygonInfo:
    is_valid = polygon.is_valid
    validity_message = "Geometria válida" if is_valid else explain_validity(polygon)

    return PolygonInfo(
        index=index,
        vertex_count=len(original_points),
        closed_automatically=closed_automatically,
        area_m2=format_number(polygon.area),
        perimeter_m=format_number(polygon.length),
        is_valid=is_valid,
        validity_message=validity_message,
    )


def polygons_to_svg(
    polygons: List[List[Tuple[float, float]]],
    lotes_map: dict[int, str],
    width: int = 520,
    height: int = 520,
) -> str:
    all_points = [pt for polygon in polygons for pt in polygon]

    if len(all_points) < 3:
        return '<div class="muted">Pontos insuficientes para desenhar os polígonos.</div>'

    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]

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

    bbox = (
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" '
        f'fill="white" stroke="#d1d5db" stroke-width="1" rx="10" />'
    )

    grid_lines = []
    for i in range(1, 5):
        gx = padding + i * (width - 2 * padding) / 5
        gy = padding + i * (height - 2 * padding) / 5
        grid_lines.append(
            f'<line x1="{gx:.2f}" y1="{padding}" x2="{gx:.2f}" y2="{height-padding}" stroke="#eef2f7" stroke-width="1"/>'
        )
        grid_lines.append(
            f'<line x1="{padding}" y1="{gy:.2f}" x2="{width-padding}" y2="{gy:.2f}" stroke="#eef2f7" stroke-width="1"/>'
        )

    palette = [
        ("#1d4ed8", "#93c5fd88"),
        ("#059669", "#86efac88"),
        ("#dc2626", "#fca5a588"),
        ("#7c3aed", "#c4b5fd88"),
        ("#ea580c", "#fdba7488"),
    ]

    svg_parts = [bbox, "".join(grid_lines)]

    for poly_idx, polygon in enumerate(polygons, start=1):
        svg_points = [project(p) for p in polygon]
        if svg_points[0] != svg_points[-1]:
            svg_points.append(svg_points[0])

        stroke, fill = palette[(poly_idx - 1) % len(palette)]
        polyline_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in svg_points)

        svg_parts.append(
            f'<polygon points="{polyline_str}" fill="{fill}" stroke="{stroke}" stroke-width="3" />'
        )

        for idx, (x, y) in enumerate(svg_points[:-1], start=1):
            svg_parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#111827" stroke="#ffffff" stroke-width="2" />'
            )
            svg_parts.append(
                f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" font-size="14" fill="#111827" font-weight="700">{poly_idx}.{idx}</text>'
            )

        poly_geom, _ = build_polygon(polygon)
        centroid = poly_geom.centroid
        cx, cy = project((centroid.x, centroid.y))
        lote_nome = lotes_map.get(poly_idx, f"Polígono {poly_idx}")

        svg_parts.append(
            f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="16" fill="#111827" font-weight="700">{lote_nome}</text>'
        )

    svg = f"""
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Prévia dos polígonos">
      {''.join(svg_parts)}
    </svg>
    """
    return svg


def to_kml_coords(points_utm: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    coords_wgs84 = []
    for x, y in points_utm:
        lon, lat = transformer_to_wgs84.transform(x, y)
        coords_wgs84.append((lon, lat))
    return coords_wgs84


def generate_kml_bytes(
    inscricao: str,
    operador: str,
    tipo: str,
    polygons_utm: List[List[Tuple[float, float]]],
    lotes_map: dict[int, str],
    descricoes_map: dict[int, str],
) -> bytes:
    kml = simplekml.Kml()

    colors = [
        simplekml.Color.red,
        simplekml.Color.green,
        simplekml.Color.blue,
        simplekml.Color.purple,
        simplekml.Color.orange,
    ]

    for idx, points_utm in enumerate(polygons_utm, start=1):
        polygon, closed_automatically = build_polygon(points_utm)
        if not polygon.is_valid:
            raise ValueError(f"Geometria inválida no polígono {idx}: {explain_validity(polygon)}")

        closed_points, _ = ensure_closed(points_utm)
        coords_wgs84 = to_kml_coords(closed_points)

        color = colors[(idx - 1) % len(colors)]
        nome_poligono = lotes_map.get(idx, f"Poligono_{idx}")
        descricao = descricoes_map.get(idx, "")
        area_m2 = format_number(polygon.area)
        perimetro_m = format_number(polygon.length)
        validade = "Válido" if polygon.is_valid else "Inválido"
        detalhe_tecnico = explain_validity(polygon) if not polygon.is_valid else "Geometria válida"

        pol = kml.newpolygon(name=nome_poligono)
        pol.outerboundaryis = coords_wgs84

        # Pode deixar vazio ou curto
        pol.description = descricao or ""

        pol.style.linestyle.width = 3
        pol.style.linestyle.color = color
        pol.style.polystyle.color = simplekml.Color.changealphaint(80, color)

        # Campos separados
        pol.extendeddata.newdata(name="inscricao", value=inscricao)
        pol.extendeddata.newdata(name="operador", value=operador or "")
        pol.extendeddata.newdata(name="tipo", value=tipo)
        pol.extendeddata.newdata(name="poligono", value=str(idx))
        pol.extendeddata.newdata(name="nome", value=nome_poligono)
        pol.extendeddata.newdata(name="descricao", value=descricao or "")
        pol.extendeddata.newdata(
            name="gerado_em",
            value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        pol.extendeddata.newdata(name="area_m2", value=area_m2)
        pol.extendeddata.newdata(name="perimetro_m", value=perimetro_m)
        pol.extendeddata.newdata(name="vertices", value=str(len(points_utm)))
        pol.extendeddata.newdata(
            name="fechado_automaticamente",
            value="Sim" if closed_automatically else "Não",
        )
        pol.extendeddata.newdata(name="validade", value=validade)
        pol.extendeddata.newdata(name="detalhe_tecnico", value=detalhe_tecnico)
        pol.extendeddata.newdata(name="src_entrada", value="SIRGAS 2000 / UTM 24S")
        pol.extendeddata.newdata(name="src_saida", value="WGS84 (KML)")

    return kml.kml().encode("utf-8")

def validate_input(inscricao: str, tipo: str, raw_points: str) -> Tuple[List[List[Tuple[float, float]]], str | None]:
    inscricao = inscricao.strip()
    tipo = tipo.strip()

    if not inscricao:
        return [], "Informe a inscrição."

    if tipo not in {"lote", "edificacao"}:
        return [], "Tipo inválido."

    polygons = parse_multiple_polygons(raw_points)

    if not polygons:
        return [], "Informe pelo menos um conjunto de pontos válido."

    for i, points in enumerate(polygons, start=1):
        if len(points) < 3:
            return [], f"O polígono {i} precisa ter pelo menos 3 pontos válidos."

        unique_points = set(points)
        if len(unique_points) < 3:
            return [], f"O polígono {i} tem poucos pontos distintos para formar uma geometria."

    return polygons, None


@app.route("/", methods=["GET", "POST"])
def index():
    inscricao = ""
    operador = ""
    tipo = "lote"
    pontos = ""
    error = None
    success = None
    polygon_info_list = None
    preview_svg = None
    lotes_map: dict[int, str] = {}
    descricoes_map: dict[int, str] = {}

    if request.method == "POST":
        inscricao = request.form.get("inscricao", "")
        operador = request.form.get("operador", "")
        tipo = request.form.get("tipo", "lote")
        pontos = request.form.get("pontos", "")
        action = request.form.get("action", "preview")

        polygons, error = validate_input(inscricao, tipo, pontos)

        if not error:
            if action == "invert":
                polygons = [list(reversed(p)) for p in polygons]
                pontos = multiple_polygons_to_text(polygons)
                success = "Ordem dos pontos invertida em todos os polígonos."

            lotes_map = extract_lotes_from_form(request.form, len(polygons))
            descricoes_map = extract_descricoes_from_form(request.form, len(polygons))

            polygon_info_list = []
            for idx, points in enumerate(polygons, start=1):
                polygon, closed_automatically = build_polygon(points)
                polygon_info_list.append(
                    make_polygon_info(idx, polygon, points, closed_automatically)
                )

            preview_svg = polygons_to_svg(polygons, lotes_map)

    return render_template_string(
        HTML,
        inscricao=inscricao,
        operador=operador,
        tipo=tipo,
        pontos=pontos,
        error=error,
        success=success,
        polygon_info_list=polygon_info_list,
        preview_svg=preview_svg,
        lotes_map=lotes_map,
        descricoes_map=descricoes_map,
    )


@app.route("/download-kml", methods=["POST"])
def download_kml():
    inscricao = request.form.get("inscricao", "")
    operador = request.form.get("operador", "")
    tipo = request.form.get("tipo", "lote")
    pontos = request.form.get("pontos", "")

    polygons, error = validate_input(inscricao, tipo, pontos)
    if error:
        return Response(error, status=400, mimetype="text/plain; charset=utf-8")

    for idx, points in enumerate(polygons, start=1):
        polygon, _ = build_polygon(points)
        if not polygon.is_valid:
            return Response(
                f"Geometria inválida no polígono {idx}: {explain_validity(polygon)}",
                status=400,
                mimetype="text/plain; charset=utf-8",
            )

    lotes_map = extract_lotes_from_form(request.form, len(polygons))
    descricoes_map = extract_descricoes_from_form(request.form, len(polygons))

    kml_bytes = generate_kml_bytes(
        inscricao=inscricao,
        operador=operador,
        tipo=tipo,
        polygons_utm=polygons,
        lotes_map=lotes_map,
        descricoes_map=descricoes_map,
    )

    operador_safe = sanitize_filename(operador) if operador.strip() else "SEM_OPERADOR"
    filename = f"{sanitize_filename(inscricao)}_{operador_safe}.kml"

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