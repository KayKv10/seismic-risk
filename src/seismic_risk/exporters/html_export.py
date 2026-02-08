"""HTML/Leaflet.js exporter for seismic risk results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seismic_risk.data.airport_movements import AIRPORT_MOVEMENTS, DEFAULT_MOVEMENTS
from seismic_risk.geo import felt_radius_km
from seismic_risk.history import TrendSummary
from seismic_risk.models import CountryRiskResult


def _build_geojson_data(results: list[CountryRiskResult]) -> dict[str, Any]:
    """Build GeoJSON data structure for embedding in HTML."""
    features: list[dict[str, Any]] = []

    for result in results:
        # Add airport features
        for airport in result.exposed_airports:
            pga_vals = [nq.pga_g for nq in airport.nearby_quakes if nq.pga_g is not None]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [airport.longitude, airport.latitude],
                },
                "properties": {
                    "feature_type": "airport",
                    "name": airport.name,
                    "iata_code": airport.iata_code,
                    "municipality": airport.municipality,
                    "country": result.country,
                    "iso_alpha3": result.iso_alpha3,
                    "closest_quake_km": airport.closest_quake_distance_km,
                    "exposure_score": airport.exposure_score,
                    "nearby_quake_count": len(airport.nearby_quakes),
                    "country_risk_score": result.seismic_hub_risk_score,
                    "pager_alert": result.highest_pager_alert,
                    "aircraft_movements_k": AIRPORT_MOVEMENTS.get(
                        airport.iata_code, DEFAULT_MOVEMENTS
                    ),
                    "max_pga_g": max(pga_vals) if pga_vals else None,
                },
            })

            # Add connection lines from airport to each nearby quake
            for nq in airport.nearby_quakes:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [airport.longitude, airport.latitude],
                            [nq.longitude, nq.latitude],
                        ],
                    },
                    "properties": {
                        "feature_type": "connection",
                        "airport_iata": airport.iata_code,
                        "earthquake_id": nq.earthquake_id,
                        "distance_km": nq.distance_km,
                        "exposure_contribution": nq.exposure_contribution,
                        "pga_g": nq.pga_g,
                        "mmi": nq.mmi,
                    },
                })

        # Add all earthquake features
        for eq in result.earthquakes:
            date_str = datetime.fromtimestamp(
                eq.time_ms / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d")
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [eq.longitude, eq.latitude],
                },
                "properties": {
                    "feature_type": "earthquake",
                    "earthquake_id": eq.id,
                    "magnitude": eq.magnitude,
                    "depth_km": eq.depth_km,
                    "felt_radius_km": felt_radius_km(eq.magnitude, eq.depth_km),
                    "date": date_str,
                    "place": eq.place,
                    "country": result.country,
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# HTML template with placeholders that won't conflict with CSS/JS braces
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Seismic Risk Assessment</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossorigin=""/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
            crossorigin=""></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont,
                'Segoe UI', Roboto, sans-serif;
        }
        #map { height: 100vh; width: 100%; }
        .airport-marker {
            background: none !important;
            border: none !important;
        }
        .airport-selected {
            filter: drop-shadow(0 0 6px rgba(0,100,255,0.8));
        }
        .sidebar {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            max-width: 320px;
        }
        .sidebar h3 { margin-bottom: 10px; color: #333; }
        .sidebar p { margin: 5px 0; color: #666; font-size: 14px; }
        .sidebar .stat { font-weight: bold; color: #333; }
        .top-airports {
            margin-top: 12px;
            border-top: 1px solid #eee;
            padding-top: 8px;
        }
        .top-airports h4 {
            font-size: 13px;
            color: #333;
            margin-bottom: 6px;
        }
        .top-airport-item {
            display: flex;
            align-items: center;
            font-size: 12px;
            padding: 3px 0;
            border-bottom: 1px solid #f5f5f5;
        }
        .top-airport-item .rank {
            color: #999;
            width: 18px;
            flex-shrink: 0;
        }
        .top-airport-item .iata {
            font-weight: bold;
            color: #333;
            width: 36px;
            flex-shrink: 0;
        }
        .top-airport-item .ap-name {
            flex: 1;
            color: #666;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin: 0 6px;
        }
        .top-airport-item .score {
            font-weight: bold;
            color: #dc3545;
            flex-shrink: 0;
        }
        .legend {
            position: absolute;
            bottom: 30px;
            left: 10px;
            z-index: 1000;
            background: white;
            padding: 10px 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            max-width: 200px;
        }
        .legend h4 {
            margin-bottom: 8px;
            font-size: 13px;
            color: #333;
        }
        .legend-item {
            display: flex;
            align-items: center;
            margin: 4px 0;
            font-size: 12px;
        }
        .legend-diamond {
            flex-shrink: 0;
            margin-right: 8px;
        }
        .gradient-bar {
            width: 100%;
            height: 12px;
            border-radius: 3px;
            margin: 4px 0;
        }
        .gradient-labels {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: #888;
        }
        .legend-note {
            font-size: 10px;
            color: #999;
            margin-top: 8px;
            line-height: 1.4;
        }
        .leaflet-popup-content { min-width: 200px; }
        .popup-title {
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 5px;
        }
        .popup-row {
            font-size: 12px;
            margin: 3px 0;
            color: #555;
        }
        .trend-section {
            margin-top: 12px;
            border-top: 1px solid #eee;
            padding-top: 8px;
        }
        .trend-section h4 {
            font-size: 13px;
            color: #333;
            margin-bottom: 6px;
        }
        .trend-item {
            display: flex;
            align-items: center;
            font-size: 12px;
            padding: 3px 0;
            border-bottom: 1px solid #f5f5f5;
        }
        .trend-item .iso {
            font-weight: bold;
            width: 36px;
            color: #333;
        }
        .trend-item .sparkline { flex: 1; margin: 0 6px; }
        .trend-item .delta {
            font-weight: bold;
            flex-shrink: 0;
            width: 50px;
            text-align: right;
        }
        .trend-up { color: #dc3545; }
        .trend-down { color: #28a745; }
        .trend-new { color: #6f42c1; }
        .trend-stable { color: #6c757d; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="sidebar">
        <h3>Seismic Risk Assessment</h3>
        <p>Countries: <span class="stat" id="country-count">0</span></p>
        <p>Exposed airports:
            <span class="stat" id="airport-count">0</span></p>
        <p>Earthquakes:
            <span class="stat" id="quake-count">0</span></p>
        <div class="top-airports">
            <h4>Top 5 Most Exposed</h4>
            <div id="top-airports-list"></div>
        </div>
        <div class="trend-section" id="trend-section"
             style="display:none;">
            <h4>Score Trends</h4>
            <div id="trend-list"></div>
            <p style="font-size:10px;color:#999;margin-top:4px;">
                Based on <span id="trend-days">0</span> days
                of history
            </p>
        </div>
        <p style="margin-top: 10px; font-size: 11px; color: #999;">
            Generated: __GENERATED_TIME__
        </p>
    </div>
    <div class="legend">
        <h4>Airport Exposure</h4>
        <div class="gradient-bar"
             style="background: linear-gradient(to right,
                 #28a745, #ffc107, #dc3545);">
        </div>
        <div class="gradient-labels">
            <span>Low</span><span>High</span>
        </div>

        <h4 style="margin-top: 10px;">Airport Size</h4>
        <div class="legend-item">
            <div class="legend-diamond">
                <svg width="14" height="14">
                    <polygon points="7,0 14,7 7,14 0,7"
                        fill="#888" stroke="#333"
                        stroke-width="1"/></svg>
            </div>
            &gt;300K movements/yr
        </div>
        <div class="legend-item">
            <div class="legend-diamond">
                <svg width="10" height="10">
                    <polygon points="5,0 10,5 5,10 0,5"
                        fill="#888" stroke="#333"
                        stroke-width="1"/></svg>
            </div>
            100-300K movements/yr
        </div>
        <div class="legend-item">
            <div class="legend-diamond">
                <svg width="7" height="7">
                    <polygon points="3.5,0 7,3.5 3.5,7 0,3.5"
                        fill="#888" stroke="#333"
                        stroke-width="1"/></svg>
            </div>
            &lt;100K movements/yr
        </div>

        <h4 style="margin-top: 10px;">Earthquake Shaking</h4>
        <div class="legend-item">
            <div style="width: 14px; height: 14px; border-radius: 50%;
                 background: rgb(251,191,36); opacity: 0.4;
                 margin-right: 8px; flex-shrink: 0;"></div>
            M3-4 (small area)
        </div>
        <div class="legend-item">
            <div style="width: 14px; height: 14px; border-radius: 50%;
                 background: rgb(245,158,11); opacity: 0.6;
                 margin-right: 8px; flex-shrink: 0;"></div>
            M5-6 (medium area)
        </div>
        <div class="legend-item">
            <div style="width: 14px; height: 14px; border-radius: 50%;
                 background: rgb(185,28,28); opacity: 0.8;
                 margin-right: 8px; flex-shrink: 0;"></div>
            M7+ (large area)
        </div>
        <div style="font-size: 10px; color: #999; margin-top: 4px;">
            Circle = estimated MMI V felt area
        </div>

        <p class="legend-note">
            Circle radius shows estimated area of strong
            shaking (MMI V). Click an airport to highlight
            its nearby quakes.
            Use layer controls (top-left) to toggle layers.
        </p>
    </div>

    <script>
        var data = __GEOJSON_DATA__;
        var trendData = __TREND_DATA__;

        // Categorize features
        var airports = data.features.filter(
            function(f) {
                return f.properties.feature_type === 'airport';
            }
        );
        var quakes = data.features.filter(
            function(f) {
                return f.properties.feature_type === 'earthquake';
            }
        );
        var connections = data.features.filter(
            function(f) {
                return f.properties.feature_type === 'connection';
            }
        );
        var countries = {};
        airports.forEach(function(f) {
            countries[f.properties.country] = true;
        });

        // Build set of quake IDs that appear in connections
        var connectedQuakeIds = {};
        connections.forEach(function(f) {
            connectedQuakeIds[f.properties.earthquake_id] = true;
        });
        var nearbyQuakes = quakes.filter(function(f) {
            return connectedQuakeIds[f.properties.earthquake_id] === true;
        });

        document.getElementById('country-count').textContent =
            Object.keys(countries).length;
        document.getElementById('airport-count').textContent =
            airports.length;
        document.getElementById('quake-count').textContent =
            quakes.length;

        // Top 5 most exposed airports
        var sorted = airports.slice().sort(function(a, b) {
            return b.properties.exposure_score
                - a.properties.exposure_score;
        });
        var top5 = sorted.slice(0, 5);
        var listEl = document.getElementById('top-airports-list');
        top5.forEach(function(f, i) {
            var p = f.properties;
            var item = document.createElement('div');
            item.className = 'top-airport-item';
            var nm = p.name.length > 22
                ? p.name.substring(0, 22) + '...' : p.name;
            item.innerHTML =
                '<span class="rank">' + (i + 1) + '.</span>'
                + '<span class="iata">' + p.iata_code + '</span>'
                + '<span class="ap-name">' + nm + '</span>'
                + '<span class="score">'
                + p.exposure_score.toFixed(1) + '</span>';
            listEl.appendChild(item);
        });

        // Sparkline builder (pure SVG, no dependencies)
        function buildSparkline(scores) {
            if (scores.length < 2) return '';
            var w = 80, h = 24, pad = 2;
            var min = Math.min.apply(null, scores);
            var max = Math.max.apply(null, scores);
            var range = max - min || 1;
            var step = (w - 2 * pad) / (scores.length - 1);
            var points = scores.map(function(s, i) {
                var x = pad + i * step;
                var y = h - pad
                    - ((s - min) / range) * (h - 2 * pad);
                return x.toFixed(1) + ',' + y.toFixed(1);
            }).join(' ');
            var last = scores[scores.length - 1];
            var first = scores[0];
            var color = last > first ? '#dc3545'
                : last < first ? '#28a745' : '#6c757d';
            return '<svg width="' + w + '" height="' + h
                + '" viewBox="0 0 ' + w + ' ' + h + '">'
                + '<polyline points="' + points
                + '" fill="none" stroke="' + color
                + '" stroke-width="1.5"'
                + ' stroke-linecap="round"'
                + ' stroke-linejoin="round"/></svg>';
        }

        // Populate trend sidebar section
        if (trendData !== null) {
            document.getElementById('trend-section')
                .style.display = '';
            document.getElementById('trend-days')
                .textContent = trendData.history_days;
            var seen = {};
            var trendEntries = [];
            airports.forEach(function(f) {
                var iso3 = f.properties.iso_alpha3;
                if (trendData.countries[iso3] && !seen[iso3]) {
                    seen[iso3] = true;
                    trendEntries.push({
                        iso3: iso3,
                        data: trendData.countries[iso3],
                    });
                }
            });
            trendEntries.sort(function(a, b) {
                return Math.abs(b.data.delta)
                    - Math.abs(a.data.delta);
            });
            var trendList = document
                .getElementById('trend-list');
            trendEntries.slice(0, 7).forEach(function(entry) {
                var d = entry.data;
                var item = document.createElement('div');
                item.className = 'trend-item';
                var svg = buildSparkline(d.scores);
                var deltaClass = d.direction === 'up'
                    ? 'trend-up'
                    : d.direction === 'down' ? 'trend-down'
                    : d.direction === 'new' ? 'trend-new'
                    : 'trend-stable';
                var deltaText = d.direction === 'new'
                    ? 'NEW'
                    : d.direction === 'stable' ? '~'
                    : (d.delta > 0 ? '+' : '')
                        + d.delta.toFixed(1);
                item.innerHTML =
                    '<span class="iso">' + entry.iso3
                    + '</span>'
                    + '<span class="sparkline">'
                    + svg + '</span>'
                    + '<span class="delta ' + deltaClass
                    + '">' + deltaText + '</span>';
                trendList.appendChild(item);
            });
        }

        // Initialize map
        var map = L.map('map').setView([20, 0], 2);
        L.tileLayer(
            'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            {
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/'
                    + 'copyright">OSM</a>',
                maxZoom: 18,
            }
        ).addTo(map);

        // Exposure color: green -> yellow -> red
        var maxScore = 1;
        airports.forEach(function(f) {
            if (f.properties.exposure_score > maxScore)
                maxScore = f.properties.exposure_score;
        });

        function exposureColor(score) {
            var t = Math.min(score / maxScore, 1);
            var r, g, b;
            if (t < 0.5) {
                var s = t * 2;
                r = Math.round(40 + (255 - 40) * s);
                g = Math.round(167 + (193 - 167) * s);
                b = Math.round(69 + (7 - 69) * s);
            } else {
                var s2 = (t - 0.5) * 2;
                r = Math.round(255 + (220 - 255) * s2);
                g = Math.round(193 + (53 - 193) * s2);
                b = Math.round(7 + (69 - 7) * s2);
            }
            return 'rgb(' + r + ',' + g + ',' + b + ')';
        }

        // Airport size by movement volume (3 tiers, thousands)
        function airportSize(movementsK) {
            if (movementsK >= 300) return 18;
            if (movementsK >= 100) return 13;
            return 9;
        }

        // Diamond SVG for airport markers
        function airportSVG(color, size) {
            var h = size / 2;
            var pts = h+',0 '+size+','+h+' '+h+','+size+' 0,'+h;
            return '<svg width="' + size + '" height="' + size
                + '"><polygon points="' + pts + '" fill="' + color
                + '" stroke="#333" stroke-width="1.5"'
                + ' fill-opacity="0.85"/></svg>';
        }

        // Connection layer (OFF by default)
        var maxContrib = 1;
        connections.forEach(function(f) {
            if (f.properties.exposure_contribution > maxContrib)
                maxContrib = f.properties.exposure_contribution;
        });

        var connectionLayer = L.geoJSON(
            { type: 'FeatureCollection', features: connections },
            {
                style: function(feature) {
                    var c = feature.properties.exposure_contribution;
                    var op = 0.3 + 0.5 * (c / maxContrib);
                    return {
                        color: '#666',
                        weight: 2,
                        dashArray: '6, 4',
                        opacity: op,
                    };
                },
            }
        );

        // Earthquake color by magnitude (amber -> dark red)
        function quakeColor(mag) {
            var t = Math.min(Math.max((mag - 3) / 5, 0), 1);
            var r = Math.round(251 + (185 - 251) * t);
            var g = Math.round(191 + (28 - 191) * t);
            var b = Math.round(36 + (28 - 36) * t);
            return 'rgb(' + r + ',' + g + ',' + b + ')';
        }
        function quakeOpacity(mag) {
            return 0.25 + 0.45
                * Math.min(Math.max((mag - 3) / 5, 0), 1);
        }

        // Shared earthquake rendering (geographic circles)
        function quakePointToLayer(feature, latlng) {
            var p = feature.properties;
            return L.circle(latlng, {
                radius: p.felt_radius_km * 1000,
                fillColor: quakeColor(p.magnitude),
                color: quakeColor(p.magnitude),
                weight: 1,
                opacity: 0.7,
                fillOpacity: quakeOpacity(p.magnitude),
            });
        }
        function quakePopup(feature, layer) {
            var p = feature.properties;
            layer.bindPopup(
                '<div class="popup-title">'
                + 'M' + p.magnitude + ' Earthquake</div>'
                + '<div class="popup-row">Place: '
                + p.place + '</div>'
                + '<div class="popup-row">Depth: '
                + p.depth_km + ' km</div>'
                + '<div class="popup-row">Felt radius: '
                + p.felt_radius_km + ' km</div>'
                + '<div class="popup-row">Date: '
                + p.date + '</div>'
                + '<div class="popup-row">Country: '
                + p.country + '</div>'
            );
        }

        // Two earthquake layers (both OFF by default, mutually exclusive)
        var nearbyQuakeLayer = L.geoJSON(
            { type: 'FeatureCollection', features: nearbyQuakes },
            { pointToLayer: quakePointToLayer, onEachFeature: quakePopup }
        );
        var allQuakeLayer = L.geoJSON(
            { type: 'FeatureCollection', features: quakes },
            { pointToLayer: quakePointToLayer, onEachFeature: quakePopup }
        );

        // Airport layer (ON by default)
        var airportLayer = L.geoJSON(
            { type: 'FeatureCollection', features: airports },
            {
                pointToLayer: function(feature, latlng) {
                    var p = feature.properties;
                    var color = exposureColor(p.exposure_score);
                    var size = airportSize(p.aircraft_movements_k);
                    var icon = L.divIcon({
                        html: airportSVG(color, size),
                        className: 'airport-marker',
                        iconSize: [size, size],
                        iconAnchor: [size / 2, size / 2],
                        popupAnchor: [0, -size / 2],
                    });
                    return L.marker(latlng, { icon: icon });
                },
                onEachFeature: function(feature, layer) {
                    var p = feature.properties;
                    var movements = p.aircraft_movements_k >= 10
                        ? Math.round(p.aircraft_movements_k)
                            + 'K movements/yr'
                        : 'N/A';
                    layer.bindPopup(
                        '<div class="popup-title">'
                        + p.name + '</div>'
                        + '<div class="popup-row">IATA: '
                        + p.iata_code + '</div>'
                        + '<div class="popup-row">'
                        + p.country
                        + ' (' + p.iso_alpha3 + ')</div>'
                        + '<div class="popup-row">'
                        + 'Aircraft movements: '
                        + movements + '</div>'
                        + '<div class="popup-row">'
                        + 'Exposure score: '
                        + p.exposure_score.toFixed(1) + '</div>'
                        + '<div class="popup-row">Nearby quakes: '
                        + p.nearby_quake_count + '</div>'
                        + '<div class="popup-row">Closest quake: '
                        + p.closest_quake_km + ' km</div>'
                        + '<div class="popup-row">'
                        + 'Country score: '
                        + p.country_risk_score + '</div>'
                        + (p.max_pga_g !== null
                            ? '<div class="popup-row">'
                                + 'ShakeMap PGA: '
                                + p.max_pga_g.toFixed(4)
                                + 'g</div>'
                            : '')
                        + (function() {
                            if (!trendData
                                || !trendData.countries[
                                    p.iso_alpha3])
                                return '';
                            var ct = trendData.countries[
                                p.iso_alpha3];
                            var cls = ct.direction === 'up'
                                ? 'trend-up'
                                : ct.direction === 'down'
                                ? 'trend-down'
                                : 'trend-stable';
                            var txt = ct.direction === 'new'
                                ? 'NEW'
                                : (ct.delta > 0 ? '+' : '')
                                    + ct.delta.toFixed(1);
                            var arrow = ct.direction === 'up'
                                ? '&#9650; '
                                : ct.direction === 'down'
                                ? '&#9660; '
                                : '';
                            return '<div class="popup-row">'
                                + '<span class="' + cls
                                + '">' + arrow + txt
                                + '</span> vs previous'
                                + '</div>';
                        })()
                    );
                    layer.on('click', function() {
                        justSelected = true;
                        selectAirport(p.iata_code, layer);
                    });
                },
            }
        );

        // Only airports on by default
        airportLayer.addTo(map);

        // Layer control (top-left, expanded)
        L.control.layers(null, {
            'Airports': airportLayer,
            'Quakes near airports': nearbyQuakeLayer,
            'All quakes in region': allQuakeLayer,
            'Connections': connectionLayer,
        }, { position: 'topleft', collapsed: false }).addTo(map);

        // Mutual exclusion for earthquake layers
        function syncLayerCheckbox(targetLayer, checked) {
            var id = L.stamp(targetLayer);
            var container = document.querySelector(
                '.leaflet-control-layers-overlays');
            if (!container) return;
            var inputs = container.querySelectorAll('input');
            inputs.forEach(function(input) {
                if (input.layerId === id) {
                    input.checked = checked;
                }
            });
        }

        map.on('overlayadd', function(e) {
            if (e.name === 'Quakes near airports'
                    && map.hasLayer(allQuakeLayer)) {
                map.removeLayer(allQuakeLayer);
                syncLayerCheckbox(allQuakeLayer, false);
            }
            if (e.name === 'All quakes in region'
                    && map.hasLayer(nearbyQuakeLayer)) {
                map.removeLayer(nearbyQuakeLayer);
                syncLayerCheckbox(nearbyQuakeLayer, false);
            }
        });

        map.on('overlayremove', function(e) {
            if (e.name === 'Quakes near airports'
                    || e.name === 'All quakes in region') {
                highlightedQuakes = [];
            }
        });

        // --- Click-to-highlight ---
        var selectedAirport = null;
        var highlightedConnections = [];
        var highlightedQuakes = [];
        var autoAddedLayers = [];
        var justSelected = false;

        function selectAirport(iata, markerLayer) {
            clearSelection();
            selectedAirport = iata;

            // Highlight the clicked marker
            var el = markerLayer.getElement();
            if (el) el.classList.add('airport-selected');

            // Find matching connections
            connectionLayer.eachLayer(function(layer) {
                if (layer.feature.properties.airport_iata === iata) {
                    highlightedConnections.push(layer);
                    layer.setStyle({
                        color: '#2563eb',
                        weight: 4,
                        dashArray: null,
                        opacity: 0.9,
                    });
                    layer.bringToFront();
                }
            });

            // Collect connected earthquake IDs
            var linkedQuakeIds = {};
            highlightedConnections.forEach(function(layer) {
                linkedQuakeIds[
                    layer.feature.properties.earthquake_id] = true;
            });

            // Auto-add layers if they are OFF
            if (!map.hasLayer(connectionLayer)) {
                map.addLayer(connectionLayer);
                autoAddedLayers.push(connectionLayer);
            }
            if (!map.hasLayer(nearbyQuakeLayer)
                    && !map.hasLayer(allQuakeLayer)) {
                map.addLayer(nearbyQuakeLayer);
                autoAddedLayers.push(nearbyQuakeLayer);
            }

            // Highlight matching earthquakes
            function highlightQuakeLayer(qLayer) {
                qLayer.eachLayer(function(layer) {
                    var qid = layer.feature.properties.earthquake_id;
                    if (linkedQuakeIds[qid]) {
                        layer._origStyle = {
                            radius: layer.getRadius(),
                            fillColor: layer.options.fillColor,
                            color: layer.options.color,
                            weight: layer.options.weight,
                            fillOpacity: layer.options.fillOpacity,
                        };
                        highlightedQuakes.push(layer);
                        layer.setStyle({
                            fillColor: '#ef4444',
                            color: '#dc2626',
                            weight: 2,
                            fillOpacity: 0.7,
                        });
                        layer.setRadius(
                            layer.getRadius() * 1.3);
                        layer.bringToFront();
                    }
                });
            }

            if (map.hasLayer(nearbyQuakeLayer))
                highlightQuakeLayer(nearbyQuakeLayer);
            if (map.hasLayer(allQuakeLayer))
                highlightQuakeLayer(allQuakeLayer);
        }

        function clearSelection() {
            if (!selectedAirport) return;

            // Remove airport highlight
            airportLayer.eachLayer(function(layer) {
                var el = layer.getElement();
                if (el) el.classList.remove('airport-selected');
            });

            // Reset connection styles
            highlightedConnections.forEach(function(layer) {
                connectionLayer.resetStyle(layer);
            });
            highlightedConnections = [];

            // Reset quake styles
            highlightedQuakes.forEach(function(layer) {
                if (layer._origStyle) {
                    layer.setStyle({
                        fillColor: layer._origStyle.fillColor,
                        color: layer._origStyle.color,
                        weight: layer._origStyle.weight,
                        fillOpacity: layer._origStyle.fillOpacity,
                    });
                    layer.setRadius(layer._origStyle.radius);
                }
            });
            highlightedQuakes = [];

            // Remove auto-added layers
            autoAddedLayers.forEach(function(layer) {
                map.removeLayer(layer);
            });
            autoAddedLayers = [];

            selectedAirport = null;
        }

        map.on('click', function() {
            if (justSelected) {
                justSelected = false;
                return;
            }
            clearSelection();
        });
    </script>
</body>
</html>"""


def _build_trend_data(trends: TrendSummary) -> dict[str, Any]:
    """Convert TrendSummary to a compact dict for JS embedding."""
    return {
        "date": trends.date,
        "history_days": trends.history_days,
        "countries": {
            iso3: {
                "scores": ct.scores,
                "dates": ct.dates,
                "current": ct.current_score,
                "previous": ct.previous_score,
                "delta": ct.score_delta,
                "direction": ct.trend_direction,
                "is_new": ct.is_new,
                "days_tracked": ct.days_tracked,
            }
            for iso3, ct in trends.country_trends.items()
            if not ct.is_gone
        },
    }


def export_html(
    results: list[CountryRiskResult],
    output_path: Path,
    *,
    trends: TrendSummary | None = None,
) -> Path:
    """Export risk results as a standalone HTML file with Leaflet.js map."""
    geojson_data = _build_geojson_data(results)
    generated_time = datetime.now(tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    trend_json = "null"
    if trends is not None:
        trend_json = json.dumps(
            _build_trend_data(trends)
        ).replace("</", "<\\/")

    html_content = _HTML_TEMPLATE.replace(
        "__GEOJSON_DATA__", json.dumps(geojson_data).replace("</", "<\\/")
    ).replace(
        "__TREND_DATA__", trend_json
    ).replace(
        "__GENERATED_TIME__", generated_time
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
