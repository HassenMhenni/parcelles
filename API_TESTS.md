# Démo API parcelles

Un titre, un `curl`. À jouer de haut en bas.

---

## 1. L'API et la base répondent

```bash
curl -s localhost:8000/health | jq
```

---

## 2. La liste des parcelles

```bash
curl -s localhost:8000/parcelles | jq '{type, count, premier: .features[0]}'
```

---

## 3. Une parcelle est un Feature GeoJSON

```bash
curl -s "localhost:8000/parcelles?page_size=1" | jq '.features[0]'
```

---

## 4. La pagination se pilote

```bash
curl -s "localhost:8000/parcelles?page_size=5&page=3" | jq '{count, recus: (.features|length)}'
```

---

## 5. Filtrer par attribut, sans se soucier de la casse

```bash
curl -s "localhost:8000/parcelles?section=ab" | jq .count
```

---

## 6. Les 4 identifiants désignent une seule parcelle

```bash
curl -s "localhost:8000/parcelles?code_insee=31555&prefixe=806&section=AB&numero=139" | jq .count
```

---

## 7. Filtrer par rectangle de carte

```bash
curl -s "localhost:8000/parcelles?bbox=1.4400,43.6000,1.4450,43.6050" | jq .count
```

---

## 8. Inclure celles coupées par le bord

```bash
curl -s "localhost:8000/parcelles?bbox=1.4400,43.6000,1.4450,43.6050&mode=intersects" | jq .count
```

---

## 9. Filtrer par polygone quelconque

```bash
curl -s --get localhost:8000/parcelles \
  --data-urlencode 'zone={"type":"Polygon","coordinates":[[[1.44,43.60],[1.44,43.61],[1.45,43.61],[1.45,43.60],[1.44,43.60]]]}' | jq .count
```

---

## 10. Un bbox aplati est refusé, pas ignoré

```bash
curl -s "localhost:8000/parcelles?bbox=1.44,43.60,1.44,43.61" | jq
```

---

## 11. Un polygone qui se croise ne part jamais dans PostGIS

```bash
curl -s --get localhost:8000/parcelles \
  --data-urlencode 'zone={"type":"Polygon","coordinates":[[[1.44,43.60],[1.45,43.61],[1.45,43.60],[1.44,43.61],[1.44,43.60]]]}' | jq
```

---

## 12. Un mode inconnu est rejeté par liste blanche

```bash
curl -s "localhost:8000/parcelles?bbox=1.44,43.60,1.45,43.61&mode=touches" | jq
```

---

## 13. Créer une parcelle — noter l'`id` renvoyé

```bash
curl -s -X POST localhost:8000/parcelles -H 'Content-Type: application/json' -d '{
  "type": "Feature",
  "geometry": {"type":"Polygon","coordinates":[[[1.0,43.0],[1.001,43.0],[1.001,43.001],[1.0,43.001],[1.0,43.0]]]},
  "properties": {"code_insee":"31555","prefixe":"999","section":"ZZ","numero":"1"}
}' | jq
```

---

## 14. Deux parcelles peuvent partager une frontière

```bash
curl -s -X POST localhost:8000/parcelles -H 'Content-Type: application/json' -d '{
  "type": "Feature",
  "geometry": {"type":"Polygon","coordinates":[[[1.001,43.0],[1.002,43.0],[1.002,43.001],[1.001,43.001],[1.001,43.0]]]},
  "properties": {"code_insee":"31555","prefixe":"999","section":"ZZ","numero":"2"}
}' | jq
```

---

## 15. Mais elles ne peuvent pas se chevaucher

```bash
curl -s -X POST localhost:8000/parcelles -H 'Content-Type: application/json' -d '{
  "type": "Feature",
  "geometry": {"type":"Polygon","coordinates":[[[1.0005,43.0005],[1.0015,43.0005],[1.0015,43.0015],[1.0005,43.0015],[1.0005,43.0005]]]},
  "properties": {"code_insee":"31555","prefixe":"999","section":"ZZ","numero":"9"}
}' | jq
```

---

## 16. Un identifiant déjà pris est un conflit, pas une erreur de saisie

```bash
curl -s -X POST localhost:8000/parcelles -H 'Content-Type: application/json' -d '{
  "type": "Feature",
  "geometry": {"type":"Polygon","coordinates":[[[1.0,43.2],[1.001,43.2],[1.001,43.201],[1.0,43.201],[1.0,43.2]]]},
  "properties": {"code_insee":"31555","prefixe":"806","section":"AB","numero":"139"}
}' | jq
```

---

## 17. Un identifiant mal formé, lui, est une erreur de saisie

```bash
curl -s -X POST localhost:8000/parcelles -H 'Content-Type: application/json' -d '{
  "type": "Feature",
  "geometry": {"type":"Polygon","coordinates":[[[1.0,43.3],[1.001,43.3],[1.001,43.301],[1.0,43.301],[1.0,43.3]]]},
  "properties": {"code_insee":"3155","prefixe":"999","section":"ABC","numero":"1"}
}' | jq
```

---

## 18. Une parcelle est un polygone, pas un point

```bash
curl -s -X POST localhost:8000/parcelles -H 'Content-Type: application/json' -d '{
  "type": "Feature",
  "geometry": {"type":"Point","coordinates":[1.0,43.3]},
  "properties": {"code_insee":"31555","prefixe":"999","section":"ZZ","numero":"14"}
}' | jq
```

---

## 19. Lire la parcelle créée

```bash
curl -s localhost:8000/parcelles/8522 | jq
```

---

## 20. Ses voisines

```bash
curl -s localhost:8000/parcelles/8522/voisines | jq '{count, ids: [.features[].id]}'
```

---

## 21. Modifier un seul champ

```bash
curl -s -X PATCH localhost:8000/parcelles/8522 -H 'Content-Type: application/json' \
  -d '{"properties":{"numero":"7"}}' | jq .properties
```

---

## 22. Changer la géométrie recalcule la surface

```bash
curl -s -X PATCH localhost:8000/parcelles/8522 -H 'Content-Type: application/json' \
  -d '{"geometry":{"type":"Polygon","coordinates":[[[1.0,43.0],[1.0005,43.0],[1.0005,43.0005],[1.0,43.0005],[1.0,43.0]]]}}' \
  | jq '{bbox, surface_m2: .properties.surface_m2}'
```

---

## 23. Déplacer une parcelle sur sa voisine reste interdit

```bash
curl -s -X PATCH localhost:8000/parcelles/8522 -H 'Content-Type: application/json' \
  -d '{"geometry":{"type":"Polygon","coordinates":[[[1.0005,43.0005],[1.0015,43.0005],[1.0015,43.0015],[1.0005,43.0015],[1.0005,43.0005]]]}}' | jq
```

---

## 24. PUT remplace tout : la géométrie est obligatoire

```bash
curl -s -X PUT localhost:8000/parcelles/8522 -H 'Content-Type: application/json' \
  -d '{"properties":{"code_insee":"31555","prefixe":"999","section":"ZZ","numero":"7"}}' | jq
```

---

## 25. Supprimer

```bash
curl -i -s -X DELETE localhost:8000/parcelles/8522 | head -1
```

---

## 26. Elle n'existe plus

```bash
curl -s localhost:8000/parcelles/8522 | jq
```

---

## 27. Un verbe hors sujet est refusé par la route

```bash
curl -s -X DELETE localhost:8000/parcelles | jq
```

---

## 28. Nettoyage

```bash
curl -s -X DELETE localhost:8000/parcelles/8523 -o /dev/null -w '%{http_code}\n'
```
