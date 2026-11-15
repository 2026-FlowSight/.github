import json
from qdrant_client import QdrantClient


def generate_html(qdrant_client, output_file="dashboard.html"):
    print("Generujem dashboard...")

    records, _ = qdrant_client.scroll(
        collection_name="vehicles_dashboard",
        limit=10000,
        with_payload=True,
        with_vectors=False
    )

    vehicles_data = []
    for r in records:
        p = r.payload
        vehicles_data.append({
            "id": p.get("original_id", "unknown")[:8],
            "full_id": p.get("original_id", ""),
            "best_frame": p.get("best_frame_path", ""),
            "timestamp": p.get("timestamp", ""),
            "camera": p.get("camera", ""),
            "views": p.get("views", [])
        })

    html_content = f"""
<!DOCTYPE html>
<html lang="sk">
<head>
    <meta charset="UTF-8">
    <title>Multi-View Vehicle Dashboard</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #1e1e1e; color: #fff; margin: 0; padding: 20px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
        .card {{ background: #2d2d2d; border-radius: 10px; overflow: hidden; cursor: pointer; transition: 0.2s; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
        .card:hover {{ transform: scale(1.02); }}
        .card img {{ width: 100%; height: 220px; object-fit: cover; display: block; }}
        .info {{ padding: 15px; }}
        .badge {{ background: #007bff; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 14px; }}
        .meta {{ font-size: 13px; color: #aaa; margin-top: 10px; }}

        /* Lightbox */
        .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 1000; flex-direction: column; justify-content: center; align-items: center; }}
        .modal.active {{ display: flex; }}

        .modal-content {{ position: relative; width: 90%; max-width: 1200px; }}
        .main-image {{ width: 100%; max-height: 70vh; object-fit: contain; border-radius: 8px; background: #000; }}

        .thumbnails {{ display: flex; gap: 10px; margin-top: 20px; justify-content: center; overflow-x: auto; }}
        .thumb {{ width: 120px; height: 90px; object-fit: cover; border-radius: 6px; cursor: pointer; opacity: 0.5; border: 3px solid transparent; transition: 0.2s; }}
        .thumb:hover, .thumb.active {{ opacity: 1; border-color: #007bff; transform: scale(1.05); }}

        .close-btn {{ position: absolute; top: -40px; right: 0; color: white; font-size: 40px; cursor: pointer; }}
        .nav-btn {{ position: absolute; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.2); color: white; border: none; padding: 20px; font-size: 30px; cursor: pointer; border-radius: 50%; }}
        .nav-btn:hover {{ background: rgba(255,255,255,0.5); }}
        .prev {{ left: -60px; }}
        .next {{ right: -60px; }}

        .title {{ text-align: center; margin-top: 15px; font-size: 20px; }}
    </style>
</head>
<body>
    <h1>Detekované vozidlá</h1>
    <div class="grid" id="grid"></div>

    <div class="modal" id="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal()">&times;</span>
            <img src="" class="main-image" id="modal-img">
            <button class="nav-btn prev" onclick="prevImage()">&#10094;</button>
            <button class="nav-btn next" onclick="nextImage()">&#10095;</button>
            <div class="title" id="modal-title"></div>
            <div class="thumbnails" id="modal-thumbs"></div>
        </div>
    </div>

    <script>
        const vehicles = {json.dumps(vehicles_data)};
        let currVeh = 0;
        let currView = 0;

        const grid = document.getElementById('grid');
        vehicles.forEach((v, i) => {{
            let imgSrc = v.best_frame;
            if(!imgSrc && v.views.length > 0) imgSrc = v.views[0].reid_crop_path;

            grid.innerHTML += `
                <div class="card" onclick="openModal(${{i}})">
                    <img src="${{imgSrc}}">
                    <div class="info">
                        <span class="badge">ID: ${{v.id}}</span>
                        <div class="meta">
                            <b>Čas:</b> ${{v.timestamp}}<br>
                            <b>Uhlov:</b> ${{v.views.length}}
                        </div>
                    </div>
                </div>
            `;
        }});

        const modal = document.getElementById('modal');
        const modalImg = document.getElementById('modal-img');
        const modalThumbs = document.getElementById('modal-thumbs');
        const modalTitle = document.getElementById('modal-title');

        function openModal(idx) {{
            currVeh = idx;
            currView = 0;
            updateModal();
            modal.classList.add('active');
        }}

        function closeModal() {{
            modal.classList.remove('active');
        }}

        function updateModal() {{
            const v = vehicles[currVeh];
            const view = v.views[currView];

            modalImg.src = view.reid_crop_path;
            modalTitle.innerHTML = `ID: <b>${{v.id}}</b> | Uhol: <b>${{view.slot.toUpperCase()}}</b>`;

            modalThumbs.innerHTML = '';
            v.views.forEach((vl, i) => {{
                modalThumbs.innerHTML += `
                    <img src="${{vl.reid_crop_path}}" class="thumb ${{i === currView ? 'active' : ''}}" onclick="setView(${{i}})">
                `;
            }});
        }}

        function setView(idx) {{
            currView = idx;
            updateModal();
        }}

        function prevImage() {{
            currView = (currView - 1 + vehicles[currVeh].views.length) % vehicles[currVeh].views.length;
            updateModal();
        }}

        function nextImage() {{
            currView = (currView + 1) % vehicles[currVeh].views.length;
            updateModal();
        }}

        document.addEventListener('keydown', (e) => {{
            if(!modal.classList.contains('active')) return;
            if(e.key === 'ArrowLeft') prevImage();
            if(e.key === 'ArrowRight') nextImage();
            if(e.key === 'Escape') closeModal();
        }});
    </script>
</body>
</html>
    """
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Dashboard vygenerovaný!")
