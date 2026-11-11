-- =====================================================================
--  BASE DE DATOS PARA LOS TESTS DEL BACKEND
--
--  Es la base actual del laboratorio con datos de prueba conocidos:
--    - Esquema: levi-db-scripts v2.0 + v2.1 (catálogo) + v2.2 + v2.3 + v2.4 + v2.5.
--    - participante: A001 Camila Rojas y A002 Matías Soto (alumnos);
--                    A015 (código sin alumno, con una sesión).
--    - sesion 1: A001 · T0 · 2026-11-04T09:15:00 · importada (8 eventos)
--      sesion 2: A001 · N1 · 2026-11-05T10:31:12 · visor     (9 eventos)
--      sesion 3: A015 · N1 · 2026-11-10T23:07:51 · visor     (21 eventos, JSON real de un visor)
--    - Totales: 38 eventos, 4 lecturas, 2 rechazos, 13 filas en sesion_tarea.
--    - lector: 2 correos ficticios (@ejemplo.cl), no los reales, SIN clave
--      (los tests que necesitan entrar le ponen una).
--    - token_revocado e intento_login: vacías.
--
--  Lo carga lab/tests/runner.py en un PostgreSQL de Docker que se crea al
--  empezar los tests y se borra al terminar. Los tests del DAO dependen de
--  estos datos: si se cambian, hay que revisar lab/tests/dao/.
--
--  Si cambia el esquema (nueva versión en levi-db-scripts), se vuelve a generar:
--  base nueva -> scripts de levi-db-scripts en orden -> estos datos ->
--  pg_dump --no-owner --no-privileges --column-inserts --no-comments
-- =====================================================================

--
-- PostgreSQL database dump
--


-- Dumped from database version 16.15 (Debian 16.15-1.pgdg13+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: evento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evento (
    sesion_id bigint NOT NULL,
    orden integer NOT NULL,
    t_s numeric(9,2) NOT NULL,
    tipo text NOT NULL,
    tarea_id bigint,
    detalle text,
    etiqueta text,
    CONSTRAINT evento_tipo_check CHECK ((tipo = ANY (ARRAY['etapa'::text, 'toma'::text, 'suelta'::text, 'lectura'::text, 'rechazo'::text, 'selector'::text, 'borne'::text, 'vista'::text, 'diagnostico'::text, 'tutorial'::text, 'recentrado'::text])))
);


--
-- Name: experimento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.experimento (
    id text NOT NULL,
    titulo text NOT NULL
);


--
-- Name: intento_login; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.intento_login (
    id bigint NOT NULL,
    ip text NOT NULL,
    momento timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: intento_login_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.intento_login ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.intento_login_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: lector; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lector (
    email text NOT NULL,
    nombre text NOT NULL,
    rol text DEFAULT 'docente'::text NOT NULL,
    creado timestamp with time zone DEFAULT now() NOT NULL,
    clave text,
    CONSTRAINT lector_rol_check CHECK ((rol = ANY (ARRAY['docente'::text, 'equipo'::text])))
);


--
-- Name: lectura; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lectura (
    sesion_id bigint NOT NULL,
    orden integer NOT NULL,
    medido double precision NOT NULL,
    esperado double precision NOT NULL,
    veredicto text NOT NULL,
    intento integer NOT NULL,
    selector text,
    borne text,
    CONSTRAINT lectura_veredicto_check CHECK ((veredicto = ANY (ARRAY['Correct'::text, 'OutOfTolerance'::text, 'ReversedPolarity'::text])))
);


--
-- Name: participante; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.participante (
    codigo text NOT NULL,
    visor text,
    registrado timestamp with time zone DEFAULT now() NOT NULL,
    nombre text,
    apellido text,
    asignatura text
);


--
-- Name: rechazo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rechazo (
    sesion_id bigint NOT NULL,
    orden integer NOT NULL,
    selector text,
    borne text
);


--
-- Name: sesion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sesion (
    id bigint NOT NULL,
    participante_id text NOT NULL,
    experimento_id text NOT NULL,
    inicio timestamp without time zone NOT NULL,
    termino timestamp without time zone,
    completada boolean DEFAULT false NOT NULL,
    duracion_s numeric(9,2),
    laboratorio_s numeric(9,2),
    correctas integer DEFAULT 0 NOT NULL,
    tareas_total integer DEFAULT 0 NOT NULL,
    version_app text,
    visor_modelo text,
    recibida_en timestamp with time zone DEFAULT now() NOT NULL,
    origen text DEFAULT 'visor'::text NOT NULL,
    CONSTRAINT sesion_origen_check CHECK ((origen = ANY (ARRAY['visor'::text, 'importada'::text])))
);


--
-- Name: sesion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.sesion ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.sesion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: sesion_tarea; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sesion_tarea (
    sesion_id bigint NOT NULL,
    tarea_id bigint NOT NULL,
    intentos integer DEFAULT 0 NOT NULL,
    rechazos integer DEFAULT 0 NOT NULL,
    veredicto_final text NOT NULL,
    intento_primera_correcta integer,
    primera_lectura_s numeric(9,2),
    primera_correcta_s numeric(9,2),
    CONSTRAINT sesion_tarea_veredicto_final_check CHECK ((veredicto_final = ANY (ARRAY['Correct'::text, 'OutOfTolerance'::text, 'ReversedPolarity'::text, 'SinRegistrar'::text])))
);


--
-- Name: tarea; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tarea (
    id bigint NOT NULL,
    experimento_id text NOT NULL,
    codigo text NOT NULL,
    magnitud text NOT NULL,
    orden integer NOT NULL,
    CONSTRAINT tarea_magnitud_check CHECK ((magnitud = ANY (ARRAY['tension'::text, 'corriente'::text])))
);


--
-- Name: tarea_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.tarea ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.tarea_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: token_revocado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_revocado (
    jti text NOT NULL,
    expira timestamp with time zone NOT NULL
);


--
-- Name: v_eventos; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_eventos AS
 SELECT ev.sesion_id,
    s.participante_id AS participant_code,
    s.experimento_id AS experiment_id,
    ev.orden,
    ev.t_s,
    ev.tipo,
    COALESCE(t.codigo, ev.etiqueta) AS tarea,
    ev.detalle,
    l.medido,
    l.esperado,
    l.veredicto,
    l.intento,
    COALESCE(l.selector, r.selector) AS selector,
    COALESCE(l.borne, r.borne) AS borne
   FROM ((((public.evento ev
     JOIN public.sesion s ON ((s.id = ev.sesion_id)))
     LEFT JOIN public.tarea t ON ((t.id = ev.tarea_id)))
     LEFT JOIN public.lectura l ON (((l.sesion_id = ev.sesion_id) AND (l.orden = ev.orden))))
     LEFT JOIN public.rechazo r ON (((r.sesion_id = ev.sesion_id) AND (r.orden = ev.orden))));


--
-- Name: v_sesiones; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_sesiones AS
 SELECT s.id AS sesion_id,
    s.participante_id AS participant_code,
    s.experimento_id AS experiment_id,
    e.titulo AS experimento,
    s.inicio,
    s.termino,
    s.completada,
    s.duracion_s,
    s.laboratorio_s,
    s.correctas,
    s.tareas_total AS tareas,
    ev.tomas,
    ev.sueltas,
    ev.sueltas_conectadas,
    round(((ev.sueltas_conectadas)::numeric / (NULLIF(ev.sueltas, 0))::numeric), 3) AS tasa_conexion,
    ev.rechazos,
    ev.ayudas,
    ev.recentrados,
    s.version_app,
    s.visor_modelo AS visor,
    s.recibida_en,
    row_number() OVER (PARTITION BY s.participante_id, s.experimento_id ORDER BY s.inicio, s.id) AS n_sesion,
    (s.completada AND (NOT (EXISTS ( SELECT 1
           FROM public.sesion p
          WHERE ((p.participante_id = s.participante_id) AND (p.experimento_id = s.experimento_id) AND p.completada AND (ROW(p.inicio, p.id) < ROW(s.inicio, s.id))))))) AS cuenta,
    s.origen
   FROM ((public.sesion s
     JOIN public.experimento e ON ((e.id = s.experimento_id)))
     LEFT JOIN LATERAL ( SELECT count(*) FILTER (WHERE (v.tipo = 'toma'::text)) AS tomas,
            count(*) FILTER (WHERE (v.tipo = 'suelta'::text)) AS sueltas,
            count(*) FILTER (WHERE ((v.tipo = 'suelta'::text) AND (v.detalle ~~ '%:conectada'::text))) AS sueltas_conectadas,
            count(*) FILTER (WHERE (v.tipo = 'rechazo'::text)) AS rechazos,
            count(*) FILTER (WHERE (v.tipo = 'vista'::text)) AS ayudas,
            count(*) FILTER (WHERE ((v.tipo = 'recentrado'::text) AND (v.detalle <> 'inicio'::text))) AS recentrados
           FROM public.evento v
          WHERE (v.sesion_id = s.id)) ev ON (true));


--
-- Name: v_participantes; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_participantes AS
 SELECT participant_code,
    experiment_id,
    count(*) AS sesiones,
    count(*) FILTER (WHERE completada) AS completadas,
    count(*) FILTER (WHERE (NOT completada)) AS incompletas,
    max(sesion_id) FILTER (WHERE cuenta) AS sesion_que_cuenta
   FROM public.v_sesiones
  GROUP BY participant_code, experiment_id;


--
-- Name: v_tareas; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_tareas AS
 SELECT st.sesion_id,
    s.participante_id AS participant_code,
    s.experimento_id AS experiment_id,
    t.codigo AS tarea,
    t.magnitud,
    st.intentos,
    st.rechazos,
    st.veredicto_final,
    st.intento_primera_correcta,
    st.primera_lectura_s,
    st.primera_correcta_s
   FROM ((public.sesion_tarea st
     JOIN public.sesion s ON ((s.id = st.sesion_id)))
     JOIN public.tarea t ON ((t.id = st.tarea_id)));


--
-- Data for Name: evento; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (1, 1, 0.00, 'etapa', NULL, 'Briefing', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (1, 2, 3.20, 'tutorial', NULL, 'cumplido', 'comenzar');
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (1, 3, 8.75, 'tutorial', NULL, 'cumplido', 'tomar');
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (1, 4, 15.10, 'tutorial', NULL, 'cumplido', 'selector');
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (1, 5, 20.00, 'etapa', NULL, 'Laboratory', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (1, 6, 24.50, 'rechazo', 1, 'MeterOff', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (1, 7, 30.25, 'lectura', 1, NULL, NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (1, 8, 35.00, 'etapa', NULL, 'Results', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 1, 0.00, 'etapa', NULL, 'Briefing', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 2, 0.43, 'recentrado', NULL, 'inicio', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 3, 5.50, 'vista', NULL, 'esquema', 'pizarra');
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 4, 9.00, 'tutorial', NULL, 'cumplido', 'selector');
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 5, 26.86, 'diagnostico', NULL, 'ExcessivePower: ''R2'' disipa 0,4236 W frente a 0,25 W nominales.', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 6, 44.26, 'etapa', NULL, 'Laboratory', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 7, 47.65, 'lectura', 8, NULL, NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 8, 50.00, 'rechazo', 9, 'OverRange', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (2, 9, 830.50, 'etapa', NULL, 'Results', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 1, 0.00, 'etapa', NULL, 'Briefing', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 2, 0.43, 'recentrado', NULL, 'inicio', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 3, 2.76, 'toma', NULL, 'Multimetro', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 4, 3.50, 'suelta', NULL, 'Multimetro:sin conectar', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 5, 26.86, 'selector', NULL, '200m V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 6, 26.86, 'diagnostico', NULL, 'ExcessivePower: ''R2'' disipa 0,4236 W frente a 0,25 W nominales. Un componente real se dañaría.', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 7, 26.86, 'diagnostico', NULL, 'ExcessivePower: ''R1'' disipa 0,2553 W frente a 0,25 W nominales. Un componente real se dañaría.', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 8, 26.92, 'selector', NULL, 'OFF', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 9, 27.86, 'selector', NULL, '200m V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 10, 27.92, 'selector', NULL, '2 V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 11, 28.06, 'selector', NULL, '20 V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 12, 28.47, 'selector', NULL, '2 V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 13, 29.31, 'selector', NULL, '20 V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 14, 29.37, 'selector', NULL, '200 V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 15, 29.42, 'selector', NULL, '600 V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 16, 29.56, 'selector', NULL, '200 V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 17, 29.71, 'selector', NULL, '20 V', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 18, 44.26, 'etapa', NULL, 'Laboratory', NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 19, 47.65, 'lectura', 8, NULL, NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 20, 49.54, 'lectura', 9, NULL, NULL);
INSERT INTO public.evento (sesion_id, orden, t_s, tipo, tarea_id, detalle, etiqueta) VALUES (3, 21, 55.22, 'etapa', NULL, 'Results', NULL);


--
-- Data for Name: experimento; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.experimento (id, titulo) VALUES ('T0', 'Tutorial: controles y primer circuito');
INSERT INTO public.experimento (id, titulo) VALUES ('N1D', 'Ley de Ohm en un circuito mixto (armado desde cero)');
INSERT INTO public.experimento (id, titulo) VALUES ('N1', 'Ley de Ohm en un circuito mixto');


--
-- Data for Name: intento_login; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: lector; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.lector (email, nombre, rol, creado, clave) VALUES ('docente@ejemplo.cl', 'Docente de prueba', 'docente', '2026-11-03 15:00:00+00', NULL);
INSERT INTO public.lector (email, nombre, rol, creado, clave) VALUES ('equipo@ejemplo.cl', 'Equipo de prueba', 'equipo', '2026-11-03 15:00:00+00', NULL);


--
-- Data for Name: lectura; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.lectura (sesion_id, orden, medido, esperado, veredicto, intento, selector, borne) VALUES (1, 7, 2.5, 2.4876, 'Correct', 1, '20 V', 'VoltOhmMilliamp');
INSERT INTO public.lectura (sesion_id, orden, medido, esperado, veredicto, intento, selector, borne) VALUES (2, 7, 4.98, 4.98400921069464, 'Correct', 1, '20 V', 'VoltOhmMilliamp');
INSERT INTO public.lectura (sesion_id, orden, medido, esperado, veredicto, intento, selector, borne) VALUES (3, 19, 3.38, 4.98400921069464, 'OutOfTolerance', 1, '20 V', 'VoltOhmMilliamp');
INSERT INTO public.lectura (sesion_id, orden, medido, esperado, veredicto, intento, selector, borne) VALUES (3, 20, 3.38, 3.384930280158629, 'Correct', 1, '20 V', 'VoltOhmMilliamp');


--
-- Data for Name: participante; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.participante (codigo, visor, registrado, nombre, apellido, asignatura) VALUES ('A001', 'A', '2026-11-03 15:00:00+00', 'Camila', 'Rojas', 'Electrónica Digital');
INSERT INTO public.participante (codigo, visor, registrado, nombre, apellido, asignatura) VALUES ('A002', 'A', '2026-11-03 15:05:00+00', 'Matías', 'Soto', 'Electrónica Digital');
INSERT INTO public.participante (codigo, visor, registrado, nombre, apellido, asignatura) VALUES ('A015', 'A', '2026-11-11 02:09:00+00', NULL, NULL, NULL);


--
-- Data for Name: rechazo; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.rechazo (sesion_id, orden, selector, borne) VALUES (1, 6, 'OFF', 'VoltOhmMilliamp');
INSERT INTO public.rechazo (sesion_id, orden, selector, borne) VALUES (2, 8, '200m V', 'VoltOhmMilliamp');


--
-- Data for Name: sesion; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.sesion (id, participante_id, experimento_id, inicio, termino, completada, duracion_s, laboratorio_s, correctas, tareas_total, version_app, visor_modelo, recibida_en, origen) OVERRIDING SYSTEM VALUE VALUES (1, 'A001', 'T0', '2026-11-04 09:15:00', '2026-11-04 09:15:35', true, 35.00, 15.00, 1, 1, '0.9-feria', 'Meta Quest 3S', '2026-11-04 12:40:00+00', 'importada');
INSERT INTO public.sesion (id, participante_id, experimento_id, inicio, termino, completada, duracion_s, laboratorio_s, correctas, tareas_total, version_app, visor_modelo, recibida_en, origen) OVERRIDING SYSTEM VALUE VALUES (2, 'A001', 'N1', '2026-11-05 10:31:12', '2026-11-05 10:45:02', true, 830.50, 700.25, 1, 6, '0.9-feria', 'Meta Quest 3S', '2026-11-05 13:46:00+00', 'visor');
INSERT INTO public.sesion (id, participante_id, experimento_id, inicio, termino, completada, duracion_s, laboratorio_s, correctas, tareas_total, version_app, visor_modelo, recibida_en, origen) OVERRIDING SYSTEM VALUE VALUES (3, 'A015', 'N1', '2026-11-10 23:07:51', '2026-11-10 23:08:46', true, 55.22, 10.96, 1, 6, '0.9-feria', 'A620M Pro RS WiFi (ASRock)', '2026-11-11 02:09:00+00', 'visor');


--
-- Data for Name: sesion_tarea; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (1, 1, 1, 1, 'Correct', 1, 30.25, 30.25);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (2, 8, 1, 0, 'Correct', 1, 47.65, 47.65);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (2, 9, 0, 1, 'SinRegistrar', NULL, NULL, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (2, 10, 0, 0, 'SinRegistrar', NULL, NULL, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (2, 11, 0, 0, 'SinRegistrar', NULL, NULL, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (2, 12, 0, 0, 'SinRegistrar', NULL, NULL, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (2, 13, 0, 0, 'SinRegistrar', NULL, NULL, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (3, 8, 1, 0, 'OutOfTolerance', NULL, 47.65, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (3, 9, 1, 0, 'Correct', 1, 49.54, 49.54);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (3, 10, 0, 0, 'SinRegistrar', NULL, NULL, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (3, 11, 0, 0, 'SinRegistrar', NULL, NULL, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (3, 12, 0, 0, 'SinRegistrar', NULL, NULL, NULL);
INSERT INTO public.sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final, intento_primera_correcta, primera_lectura_s, primera_correcta_s) VALUES (3, 13, 0, 0, 'SinRegistrar', NULL, NULL, NULL);


--
-- Data for Name: tarea; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (1, 'T0', 'V_R1', 'tension', 1);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (2, 'N1D', 'V1', 'tension', 1);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (3, 'N1D', 'V2', 'tension', 2);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (4, 'N1D', 'V3', 'tension', 3);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (5, 'N1D', 'I_total', 'corriente', 4);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (6, 'N1D', 'I_R2', 'corriente', 5);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (7, 'N1D', 'I_R4', 'corriente', 6);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (8, 'N1', 'V1', 'tension', 1);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (9, 'N1', 'V2', 'tension', 2);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (10, 'N1', 'V3', 'tension', 3);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (11, 'N1', 'I_total', 'corriente', 4);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (12, 'N1', 'I_R2', 'corriente', 5);
INSERT INTO public.tarea (id, experimento_id, codigo, magnitud, orden) OVERRIDING SYSTEM VALUE VALUES (13, 'N1', 'I_R4', 'corriente', 6);


--
-- Data for Name: token_revocado; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Name: intento_login_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.intento_login_id_seq', 1, false);


--
-- Name: sesion_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.sesion_id_seq', 3, true);


--
-- Name: tarea_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.tarea_id_seq', 13, true);


--
-- Name: evento evento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento
    ADD CONSTRAINT evento_pkey PRIMARY KEY (sesion_id, orden);


--
-- Name: experimento experimento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experimento
    ADD CONSTRAINT experimento_pkey PRIMARY KEY (id);


--
-- Name: intento_login intento_login_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intento_login
    ADD CONSTRAINT intento_login_pkey PRIMARY KEY (id);


--
-- Name: lector lector_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lector
    ADD CONSTRAINT lector_pkey PRIMARY KEY (email);


--
-- Name: lectura lectura_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lectura
    ADD CONSTRAINT lectura_pkey PRIMARY KEY (sesion_id, orden);


--
-- Name: participante participante_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.participante
    ADD CONSTRAINT participante_pkey PRIMARY KEY (codigo);


--
-- Name: rechazo rechazo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rechazo
    ADD CONSTRAINT rechazo_pkey PRIMARY KEY (sesion_id, orden);


--
-- Name: sesion sesion_participante_id_experimento_id_inicio_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion
    ADD CONSTRAINT sesion_participante_id_experimento_id_inicio_key UNIQUE (participante_id, experimento_id, inicio);


--
-- Name: sesion sesion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion
    ADD CONSTRAINT sesion_pkey PRIMARY KEY (id);


--
-- Name: sesion_tarea sesion_tarea_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_tarea
    ADD CONSTRAINT sesion_tarea_pkey PRIMARY KEY (sesion_id, tarea_id);


--
-- Name: tarea tarea_experimento_id_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarea
    ADD CONSTRAINT tarea_experimento_id_codigo_key UNIQUE (experimento_id, codigo);


--
-- Name: tarea tarea_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarea
    ADD CONSTRAINT tarea_pkey PRIMARY KEY (id);


--
-- Name: token_revocado token_revocado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_revocado
    ADD CONSTRAINT token_revocado_pkey PRIMARY KEY (jti);


--
-- Name: evento_tipo_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX evento_tipo_idx ON public.evento USING btree (tipo);


--
-- Name: intento_login_ip_momento_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX intento_login_ip_momento_idx ON public.intento_login USING btree (ip, momento);


--
-- Name: sesion_experimento_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sesion_experimento_idx ON public.sesion USING btree (experimento_id);


--
-- Name: sesion_inicio_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sesion_inicio_idx ON public.sesion USING btree (inicio);


--
-- Name: token_revocado_expira_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX token_revocado_expira_idx ON public.token_revocado USING btree (expira);


--
-- Name: evento evento_sesion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento
    ADD CONSTRAINT evento_sesion_id_fkey FOREIGN KEY (sesion_id) REFERENCES public.sesion(id) ON DELETE CASCADE;


--
-- Name: evento evento_tarea_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evento
    ADD CONSTRAINT evento_tarea_id_fkey FOREIGN KEY (tarea_id) REFERENCES public.tarea(id);


--
-- Name: lectura lectura_sesion_id_orden_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lectura
    ADD CONSTRAINT lectura_sesion_id_orden_fkey FOREIGN KEY (sesion_id, orden) REFERENCES public.evento(sesion_id, orden) ON DELETE CASCADE;


--
-- Name: rechazo rechazo_sesion_id_orden_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rechazo
    ADD CONSTRAINT rechazo_sesion_id_orden_fkey FOREIGN KEY (sesion_id, orden) REFERENCES public.evento(sesion_id, orden) ON DELETE CASCADE;


--
-- Name: sesion sesion_experimento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion
    ADD CONSTRAINT sesion_experimento_id_fkey FOREIGN KEY (experimento_id) REFERENCES public.experimento(id);


--
-- Name: sesion sesion_participante_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion
    ADD CONSTRAINT sesion_participante_id_fkey FOREIGN KEY (participante_id) REFERENCES public.participante(codigo);


--
-- Name: sesion_tarea sesion_tarea_sesion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_tarea
    ADD CONSTRAINT sesion_tarea_sesion_id_fkey FOREIGN KEY (sesion_id) REFERENCES public.sesion(id) ON DELETE CASCADE;


--
-- Name: sesion_tarea sesion_tarea_tarea_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_tarea
    ADD CONSTRAINT sesion_tarea_tarea_id_fkey FOREIGN KEY (tarea_id) REFERENCES public.tarea(id);


--
-- Name: tarea tarea_experimento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tarea
    ADD CONSTRAINT tarea_experimento_id_fkey FOREIGN KEY (experimento_id) REFERENCES public.experimento(id);


--
-- PostgreSQL database dump complete
--


