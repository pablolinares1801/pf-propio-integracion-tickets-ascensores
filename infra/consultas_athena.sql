-- Consultas de ejemplo sobre la tabla catalogada por el Glue Crawler
-- (pf_propio_tickets_db, tabla autogenerada a partir de /procesados/validos/).
-- Pensadas para la Sección 4 (Implementación) y la demostración en vivo:
-- muestran valor analítico real sobre los tickets ya integrados, el tipo de
-- pregunta que hoy la empresa no puede responder porque los datos viven
-- sueltos en tres formatos distintos.

-- 1) Volumen de tickets válidos por canal de origen
SELECT canal, COUNT(*) AS total_tickets
FROM validos
GROUP BY canal
ORDER BY total_tickets DESC;

-- 2) Tickets por sucursal (para priorizar visitas técnicas)
SELECT sucursal, COUNT(*) AS total_tickets
FROM validos
GROUP BY sucursal
ORDER BY total_tickets DESC;

-- 3) Tickets por marca de ascensor (para detectar si una marca concentra
--    más reportes de falla que las demás)
SELECT marca_ascensor, COUNT(*) AS total_tickets
FROM validos
GROUP BY marca_ascensor
ORDER BY total_tickets DESC;

-- 4) Cruce sucursal x marca, útil como insumo de la futura Capa 1 (tesis):
--    saber dónde concentrar el etiquetado retrospectivo de urgencia primero
SELECT sucursal, marca_ascensor, COUNT(*) AS total_tickets
FROM validos
GROUP BY sucursal, marca_ascensor
ORDER BY sucursal, total_tickets DESC;
