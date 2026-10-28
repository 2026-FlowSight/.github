import os
from qdrant_client import QdrantClient


def generate_html(qclient=None, output_path="static/index.html", collection_name="vehicles", db_path ="./qdrant_demo"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)


    client = qclient if qclient is not None else QdrantClient(path=db_path)

    try:
        points, _ = client.scroll(collection_name=collection_name, limit=1000, with_payload=True)
    except Exception as e:
        print(f"Chyba pri čítaní z databázy: {e}")
        return

    html_content = """
    <!DOCTYPE html>
    <html lang="sk">
    <head>
        <meta charset="UTF-8">
        <title>Demo - Nájdené vozidlá (ReID)</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f5f7fa; margin: 20px; }
            h1 { color: #333; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }
            .card { 
                background: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
                padding: 15px; display: flex; flex-direction: column; 
            }
            /* Kontajner, ktorý presne kopíruje rozmery obrázka */
             .image-container {
                position: relative;
                width: 100%;
                aspect-ratio: 4 / 3; /* Musí sedieť s target_ratio v Pythone */
                background-color: #eee;
                border-radius: 4px;
                overflow: hidden;
            }
            
            .image-container img {
                width: 100%;
                height: 100%;
                object-fit: cover; /* KĽÚČOVÉ: Vyplní celú kartu a oreže okraje */
                object-position: center; /* Zameria sa na stred (kde je auto) */
                display: block;
            }
            /* BBOX - absolútne pozicovaný */
            .bbox {
                position: absolute;
                border: 2px solid #ff0000; /* Červený rámik */
                box-sizing: border-box;
                background-color: rgba(255, 0, 0, 0.1); /* Jemnučká červená výplň */
                box-shadow: 0 0 5px rgba(255, 0, 0, 0.5);
                pointer-events: none;
            }
            .info { margin-top: 10px; font-size: 14px; color: #555; }
            .info b { color: #333; }
            .id-badge { background: #007bff; color: white; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
            .empty { text-align: center; color: #888; margin-top: 50px; grid-column: 1/-1; }

            /* LIGHTBOX */
            .modal {
                display: none; 
                position: fixed; 
                z-index: 1000; 
                left: 0; 
                top: 0;
                width: 100%; 
                height: 100%; 
                background-color: rgba(0,0,0,0.95);
                justify-content: center; 
                align-items: center; 
                flex-direction: column;
            }
            
            /* Kontajner pre obrázok v modale */
            .modal-content {
                position: relative;
                width: 95vw;          /* Takmer celá šírka obrazovky */
                height: 85vh;         /* Takmer celá výška obrazovky */
                display: flex;
                justify-content: center;
                align-items: center;
                max-width: fit-content;
            }
            
            /* Samotný obrázok v modale */
            .modal-content img {
                width: 100%;
                height: 100%;
                object-fit: contain;  /* Zobrazí celý obrázok, ale čo najväčší */
                display: block;
            }
            
            /* BBOX v modale */
            .modal-bbox {
                position: absolute;
                border: 3px solid #ff0000;
                box-sizing: border-box;
                background-color: rgba(255, 0, 0, 0.15);
                pointer-events: none;
            }
            .close-btn { position: absolute; top: 20px; right: 30px; color: #fff; font-size: 40px; cursor: pointer; }
            .modal-info { color: white; margin-top: 15px; font-size: 16px; }
        </style>
    </head>
    <body>
        <h1>Nájdené vozidlá (Vehicle ReID Demo)</h1>
        <p>Počet záznamov: <b>""" + str(len(points)) + """</b></p>
        <div class="grid">
    """

    if not points:
        html_content += "<div class='empty'>Zatiaľ neboli uložené žiadne vozidlá.</div>"
    else:
        for p in points:
            payload = p.payload
            frame_path = payload.get("frame_path", "")
            bbox = payload.get("bbox", [])
            frame_shape = payload.get("frame_shape", [720, 1280])  # Fallback
            original_id = payload.get("original_id", "N/A")
            timestamp = payload.get("timestamp", "N/A")
            camera = payload.get("camera", "N/A")
            short_id = original_id[:8] + "..." if len(original_id) > 8 else original_id

            # Výpočet pozície bboxu v percentách
            bbox_style = "display: none;"
            if bbox and len(bbox) == 4 and len(frame_shape) == 2:
                x1, y1, x2, y2 = bbox
                h_orig, w_orig = frame_shape

                if w_orig > 0 and h_orig > 0:
                    left_pct = (x1 / w_orig) * 100
                    top_pct = (y1 / h_orig) * 100
                    width_pct = ((x2 - x1) / w_orig) * 100
                    height_pct = ((y2 - y1) / h_orig) * 100

                    bbox_style = f"display: block; left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;"

            html_content += f"""
            <div class="card">
                <div class="image-container" onclick="openModal('{frame_path}', '{short_id}', '{camera}', '{timestamp}')">
                    <img src="../{frame_path}" alt="Snímok" onerror="this.src='https://via.placeholder.com/350x200?text=Snímok+chybí'">
                    <div class="bbox" style="{bbox_style}"></div>
                </div>
                <div class="info">
                    <div style="margin-bottom: 5px;"><span class="id-badge">ID: {short_id}</span></div>
                    <div><b>Kamera:</b> {camera}</div>
                    <div><b>Čas:</b> {timestamp}</div>
                </div>
            </div>
            """

    html_content += """
        </div>

        <!-- LIGHTBOX (MODAL) -->
        <div id="imageModal" class="modal" onclick="closeModal(event)">
            <span class="close-btn" onclick="closeModal(event)">&times;</span>
            <div class="modal-content" id="modalContent">
                <img id="modalImg" src="" alt="Zväčšený snímok">
            </div>
            <div class="modal-info" id="modalInfo"></div>
        </div>

        <script>
            function openModal(imgSrc, id, camera, time) {
                document.getElementById('modalImg').src = '../' + imgSrc;
                document.getElementById('modalInfo').innerHTML = `<span class="id-badge">ID: ${id}</span> | Kamera: ${camera} | Čas: ${time}`;
                document.getElementById('imageModal').style.display = 'flex';
            }

            function closeModal(event) {
                // Zavrie iba ak klikneme priamo na čierne pozadie (imageModal)
                // alebo na krížik (close-btn). Ak klikneme na obrázok, nič sa nedeje.
                if (event.target.id === 'imageModal' || event.target.classList.contains('close-btn')) {
                    document.getElementById('imageModal').style.display = 'none';
                }
            }
        </script>
    </body>
    </html>
    """

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML bolo úspešne vygenerované do: {output_path}")
    client.close()


if __name__ == "__main__":
    generate_html()