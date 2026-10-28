# DEV03: ReID Embeddingy a Qdrant Storage

## Cieľ
Pre každé nové `track_id` (alebo pri zmene najlepšieho záberu) extrahovať ReID embedding z TensorRT modelu a uložiť ho do Qdrant databázy spolu s metadátami (čas, kamera, typ vozidla).

## Vstup
- Výstup z DEV02 (detekcie s `track_id`).
- ReID TensorRT engine (napr. `vehicle_reid.engine`).
- Bežiaci Qdrant (lokálny alebo server).

## Výstup
- Qdrant kolekcia `vehicles` s bodmi (vektormi) a payloadom.
- Uložené výrezy áut na disk (napr. `frames/{id}.jpg`).

## Postup
1. Pri novom `tid` orezať výrez auta (s paddingom).
2. Spustiť ReID inferenciu (TensorRT).
3. Uložiť vektor do Qdrant (`upsert`).
4. Uložiť cestu k obrázku a metadata do payloadu.

## Definition of Done
- [ ] V Qdrant pribúdajú body pri nových autách.
- [ ] Payload obsahuje `original_id`, `frame_path`, `timestamp`, `camera`.
- [ ] Obrázky sa ukladajú do priečinka `frames/`.