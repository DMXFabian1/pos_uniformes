--
-- PostgreSQL database dump
--

\restrict EpZiEx89NdLyIxLnvg1r0iLJNUH6JkUrKUZS0KzEUBCCjFtaBUR6MsVGo5wK3jM

-- Dumped from database version 18.3 (Postgres.app)
-- Dumped by pg_dump version 18.3 (Postgres.app)

-- Started on 2026-03-10 19:20:24 CST

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 935 (class 1247 OID 16748)
-- Name: estado_apartado; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.estado_apartado AS ENUM (
    'ACTIVO',
    'LIQUIDADO',
    'ENTREGADO',
    'CANCELADO'
);


--
-- TOC entry 914 (class 1247 OID 16573)
-- Name: estado_compra; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.estado_compra AS ENUM (
    'BORRADOR',
    'CONFIRMADA',
    'CANCELADA'
);


--
-- TOC entry 920 (class 1247 OID 16614)
-- Name: estado_venta; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.estado_venta AS ENUM (
    'BORRADOR',
    'CONFIRMADA',
    'CANCELADA'
);


--
-- TOC entry 908 (class 1247 OID 16549)
-- Name: rol_usuario; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.rol_usuario AS ENUM (
    'ADMIN',
    'CAJERO'
);


--
-- TOC entry 899 (class 1247 OID 16493)
-- Name: tipo_movimiento_inventario; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tipo_movimiento_inventario AS ENUM (
    'ENTRADA_COMPRA',
    'SALIDA_VENTA',
    'AJUSTE_ENTRADA',
    'AJUSTE_SALIDA',
    'CANCELACION_VENTA',
    'APARTADO_RESERVA',
    'APARTADO_LIBERACION'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 219 (class 1259 OID 16391)
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- TOC entry 245 (class 1259 OID 16758)
-- Name: apartado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.apartado (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    cancelado_por_id integer,
    entregado_por_id integer,
    folio character varying(40) NOT NULL,
    cliente_nombre character varying(150) NOT NULL,
    cliente_telefono character varying(40),
    estado public.estado_apartado NOT NULL,
    subtotal numeric(12,2) DEFAULT 0.00 NOT NULL,
    total numeric(12,2) DEFAULT 0.00 NOT NULL,
    total_abonado numeric(12,2) DEFAULT 0.00 NOT NULL,
    saldo_pendiente numeric(12,2) DEFAULT 0.00 NOT NULL,
    fecha_compromiso timestamp with time zone,
    observacion text,
    liquidado_at timestamp with time zone,
    entregado_at timestamp with time zone,
    cancelado_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 249 (class 1259 OID 16836)
-- Name: apartado_abono; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.apartado_abono (
    id integer NOT NULL,
    apartado_id integer NOT NULL,
    usuario_id integer NOT NULL,
    monto numeric(12,2) NOT NULL,
    referencia character varying(120),
    observacion text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    metodo_pago character varying(30),
    monto_efectivo numeric(12,2),
    CONSTRAINT ck_apartado_abono_apartado_abono_monto_efectivo_no_negativo CHECK (((monto_efectivo IS NULL) OR (monto_efectivo >= (0)::numeric))),
    CONSTRAINT ck_apartado_abono_apartado_abono_monto_positivo CHECK ((monto > (0)::numeric))
);


--
-- TOC entry 248 (class 1259 OID 16835)
-- Name: apartado_abono_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.apartado_abono_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4109 (class 0 OID 0)
-- Dependencies: 248
-- Name: apartado_abono_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.apartado_abono_id_seq OWNED BY public.apartado_abono.id;


--
-- TOC entry 247 (class 1259 OID 16807)
-- Name: apartado_detalle; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.apartado_detalle (
    id integer NOT NULL,
    apartado_id integer NOT NULL,
    variante_id integer NOT NULL,
    cantidad integer NOT NULL,
    precio_unitario numeric(10,2) NOT NULL,
    subtotal_linea numeric(12,2) NOT NULL,
    CONSTRAINT ck_apartado_detalle_apartado_detalle_cantidad_positiva CHECK ((cantidad > 0)),
    CONSTRAINT ck_apartado_detalle_apartado_detalle_precio_unitario_no_928d CHECK ((precio_unitario >= (0)::numeric))
);


--
-- TOC entry 246 (class 1259 OID 16806)
-- Name: apartado_detalle_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.apartado_detalle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4110 (class 0 OID 0)
-- Dependencies: 246
-- Name: apartado_detalle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.apartado_detalle_id_seq OWNED BY public.apartado_detalle.id;


--
-- TOC entry 244 (class 1259 OID 16757)
-- Name: apartado_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.apartado_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4111 (class 0 OID 0)
-- Dependencies: 244
-- Name: apartado_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.apartado_id_seq OWNED BY public.apartado.id;


--
-- TOC entry 221 (class 1259 OID 16398)
-- Name: categoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categoria (
    id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    descripcion text,
    activo boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 220 (class 1259 OID 16397)
-- Name: categoria_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categoria_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4112 (class 0 OID 0)
-- Dependencies: 220
-- Name: categoria_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categoria_id_seq OWNED BY public.categoria.id;


--
-- TOC entry 235 (class 1259 OID 16580)
-- Name: compra; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compra (
    id integer NOT NULL,
    proveedor_id integer NOT NULL,
    usuario_id integer NOT NULL,
    numero_documento character varying(40) NOT NULL,
    estado public.estado_compra NOT NULL,
    subtotal numeric(12,2) NOT NULL,
    total numeric(12,2) NOT NULL,
    observacion text,
    confirmada_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 239 (class 1259 OID 16655)
-- Name: compra_detalle; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compra_detalle (
    id integer NOT NULL,
    compra_id integer NOT NULL,
    variante_id integer NOT NULL,
    cantidad integer NOT NULL,
    costo_unitario numeric(10,2) NOT NULL,
    subtotal_linea numeric(12,2) NOT NULL,
    CONSTRAINT ck_compra_detalle_compra_detalle_cantidad_positiva CHECK ((cantidad > 0)),
    CONSTRAINT ck_compra_detalle_compra_detalle_costo_unitario_no_negativo CHECK ((costo_unitario >= (0)::numeric))
);


--
-- TOC entry 238 (class 1259 OID 16654)
-- Name: compra_detalle_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.compra_detalle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4113 (class 0 OID 0)
-- Dependencies: 238
-- Name: compra_detalle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.compra_detalle_id_seq OWNED BY public.compra_detalle.id;


--
-- TOC entry 234 (class 1259 OID 16579)
-- Name: compra_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.compra_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4114 (class 0 OID 0)
-- Dependencies: 234
-- Name: compra_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.compra_id_seq OWNED BY public.compra.id;


--
-- TOC entry 243 (class 1259 OID 16714)
-- Name: configuracion_negocio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.configuracion_negocio (
    id integer NOT NULL,
    nombre_negocio character varying(160) NOT NULL,
    telefono character varying(40),
    direccion text,
    pie_ticket text,
    impresora_preferida character varying(200),
    copias_ticket integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    transferencia_banco character varying(120),
    transferencia_beneficiario character varying(160),
    transferencia_clabe character varying(40),
    transferencia_instrucciones text
);


--
-- TOC entry 242 (class 1259 OID 16713)
-- Name: configuracion_negocio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.configuracion_negocio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4115 (class 0 OID 0)
-- Dependencies: 242
-- Name: configuracion_negocio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.configuracion_negocio_id_seq OWNED BY public.configuracion_negocio.id;


--
-- TOC entry 223 (class 1259 OID 16415)
-- Name: marca; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.marca (
    id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    descripcion text,
    activo boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 222 (class 1259 OID 16414)
-- Name: marca_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.marca_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4116 (class 0 OID 0)
-- Dependencies: 222
-- Name: marca_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.marca_id_seq OWNED BY public.marca.id;


--
-- TOC entry 229 (class 1259 OID 16504)
-- Name: movimiento_inventario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movimiento_inventario (
    id integer NOT NULL,
    variante_id integer NOT NULL,
    tipo_movimiento public.tipo_movimiento_inventario NOT NULL,
    cantidad integer NOT NULL,
    stock_anterior integer NOT NULL,
    stock_posterior integer NOT NULL,
    referencia character varying(120),
    observacion text,
    creado_por character varying(60) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_movimiento_inventario_movimiento_inventario_cantidad_no_cero CHECK ((cantidad <> 0)),
    CONSTRAINT ck_movimiento_inventario_movimiento_inventario_stock_po_97fc CHECK ((stock_posterior >= 0))
);


--
-- TOC entry 228 (class 1259 OID 16503)
-- Name: movimiento_inventario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.movimiento_inventario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4117 (class 0 OID 0)
-- Dependencies: 228
-- Name: movimiento_inventario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.movimiento_inventario_id_seq OWNED BY public.movimiento_inventario.id;


--
-- TOC entry 225 (class 1259 OID 16432)
-- Name: producto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.producto (
    id integer NOT NULL,
    categoria_id integer NOT NULL,
    marca_id integer NOT NULL,
    nombre character varying(150) NOT NULL,
    descripcion text,
    activo boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 224 (class 1259 OID 16431)
-- Name: producto_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.producto_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4118 (class 0 OID 0)
-- Dependencies: 224
-- Name: producto_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.producto_id_seq OWNED BY public.producto.id;


--
-- TOC entry 231 (class 1259 OID 16532)
-- Name: proveedor; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proveedor (
    id integer NOT NULL,
    nombre character varying(150) NOT NULL,
    telefono character varying(30),
    email character varying(120),
    direccion text,
    activo boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 230 (class 1259 OID 16531)
-- Name: proveedor_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proveedor_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4119 (class 0 OID 0)
-- Dependencies: 230
-- Name: proveedor_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proveedor_id_seq OWNED BY public.proveedor.id;


--
-- TOC entry 251 (class 1259 OID 16864)
-- Name: sesion_caja; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sesion_caja (
    id integer NOT NULL,
    abierta_por_id integer NOT NULL,
    cerrada_por_id integer,
    monto_apertura numeric(12,2) NOT NULL,
    monto_cierre_declarado numeric(12,2),
    monto_esperado_cierre numeric(12,2),
    diferencia_cierre numeric(12,2),
    observacion_apertura text,
    observacion_cierre text,
    abierta_at timestamp with time zone DEFAULT now() NOT NULL,
    cerrada_at timestamp with time zone
);


--
-- TOC entry 250 (class 1259 OID 16863)
-- Name: sesion_caja_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sesion_caja_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4120 (class 0 OID 0)
-- Dependencies: 250
-- Name: sesion_caja_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sesion_caja_id_seq OWNED BY public.sesion_caja.id;


--
-- TOC entry 233 (class 1259 OID 16554)
-- Name: usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario (
    id integer NOT NULL,
    username character varying(60) NOT NULL,
    nombre_completo character varying(150) NOT NULL,
    password_hash character varying(255) NOT NULL,
    rol public.rol_usuario NOT NULL,
    activo boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 232 (class 1259 OID 16553)
-- Name: usuario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4121 (class 0 OID 0)
-- Dependencies: 232
-- Name: usuario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuario_id_seq OWNED BY public.usuario.id;


--
-- TOC entry 227 (class 1259 OID 16463)
-- Name: variante; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.variante (
    id integer NOT NULL,
    producto_id integer NOT NULL,
    sku character varying(64) NOT NULL,
    talla character varying(30) NOT NULL,
    color character varying(50) NOT NULL,
    precio_venta numeric(10,2) NOT NULL,
    costo_referencia numeric(10,2),
    stock_actual integer NOT NULL,
    activo boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_variante_variante_stock_actual_no_negativo CHECK ((stock_actual >= 0))
);


--
-- TOC entry 226 (class 1259 OID 16462)
-- Name: variante_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.variante_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4122 (class 0 OID 0)
-- Dependencies: 226
-- Name: variante_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.variante_id_seq OWNED BY public.variante.id;


--
-- TOC entry 237 (class 1259 OID 16622)
-- Name: venta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venta (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    cancelado_por_id integer,
    folio character varying(40) NOT NULL,
    estado public.estado_venta NOT NULL,
    subtotal numeric(12,2) NOT NULL,
    total numeric(12,2) NOT NULL,
    observacion text,
    confirmada_at timestamp with time zone,
    cancelada_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 241 (class 1259 OID 16684)
-- Name: venta_detalle; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venta_detalle (
    id integer NOT NULL,
    venta_id integer NOT NULL,
    variante_id integer NOT NULL,
    cantidad integer NOT NULL,
    precio_unitario numeric(10,2) NOT NULL,
    subtotal_linea numeric(12,2) NOT NULL,
    CONSTRAINT ck_venta_detalle_venta_detalle_cantidad_positiva CHECK ((cantidad > 0)),
    CONSTRAINT ck_venta_detalle_venta_detalle_precio_unitario_no_negativo CHECK ((precio_unitario >= (0)::numeric))
);


--
-- TOC entry 240 (class 1259 OID 16683)
-- Name: venta_detalle_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.venta_detalle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4123 (class 0 OID 0)
-- Dependencies: 240
-- Name: venta_detalle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.venta_detalle_id_seq OWNED BY public.venta_detalle.id;


--
-- TOC entry 236 (class 1259 OID 16621)
-- Name: venta_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.venta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4124 (class 0 OID 0)
-- Dependencies: 236
-- Name: venta_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.venta_id_seq OWNED BY public.venta.id;


--
-- TOC entry 3796 (class 2604 OID 16761)
-- Name: apartado id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado ALTER COLUMN id SET DEFAULT nextval('public.apartado_id_seq'::regclass);


--
-- TOC entry 3804 (class 2604 OID 16839)
-- Name: apartado_abono id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_abono ALTER COLUMN id SET DEFAULT nextval('public.apartado_abono_id_seq'::regclass);


--
-- TOC entry 3803 (class 2604 OID 16810)
-- Name: apartado_detalle id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_detalle ALTER COLUMN id SET DEFAULT nextval('public.apartado_detalle_id_seq'::regclass);


--
-- TOC entry 3764 (class 2604 OID 16401)
-- Name: categoria id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria ALTER COLUMN id SET DEFAULT nextval('public.categoria_id_seq'::regclass);


--
-- TOC entry 3784 (class 2604 OID 16583)
-- Name: compra id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra ALTER COLUMN id SET DEFAULT nextval('public.compra_id_seq'::regclass);


--
-- TOC entry 3790 (class 2604 OID 16658)
-- Name: compra_detalle id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra_detalle ALTER COLUMN id SET DEFAULT nextval('public.compra_detalle_id_seq'::regclass);


--
-- TOC entry 3792 (class 2604 OID 16717)
-- Name: configuracion_negocio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracion_negocio ALTER COLUMN id SET DEFAULT nextval('public.configuracion_negocio_id_seq'::regclass);


--
-- TOC entry 3767 (class 2604 OID 16418)
-- Name: marca id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.marca ALTER COLUMN id SET DEFAULT nextval('public.marca_id_seq'::regclass);


--
-- TOC entry 3776 (class 2604 OID 16507)
-- Name: movimiento_inventario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento_inventario ALTER COLUMN id SET DEFAULT nextval('public.movimiento_inventario_id_seq'::regclass);


--
-- TOC entry 3770 (class 2604 OID 16435)
-- Name: producto id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto ALTER COLUMN id SET DEFAULT nextval('public.producto_id_seq'::regclass);


--
-- TOC entry 3778 (class 2604 OID 16535)
-- Name: proveedor id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proveedor ALTER COLUMN id SET DEFAULT nextval('public.proveedor_id_seq'::regclass);


--
-- TOC entry 3806 (class 2604 OID 16867)
-- Name: sesion_caja id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_caja ALTER COLUMN id SET DEFAULT nextval('public.sesion_caja_id_seq'::regclass);


--
-- TOC entry 3781 (class 2604 OID 16557)
-- Name: usuario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario ALTER COLUMN id SET DEFAULT nextval('public.usuario_id_seq'::regclass);


--
-- TOC entry 3773 (class 2604 OID 16466)
-- Name: variante id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variante ALTER COLUMN id SET DEFAULT nextval('public.variante_id_seq'::regclass);


--
-- TOC entry 3787 (class 2604 OID 16625)
-- Name: venta id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta ALTER COLUMN id SET DEFAULT nextval('public.venta_id_seq'::regclass);


--
-- TOC entry 3791 (class 2604 OID 16687)
-- Name: venta_detalle id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta_detalle ALTER COLUMN id SET DEFAULT nextval('public.venta_detalle_id_seq'::regclass);


--
-- TOC entry 4071 (class 0 OID 16391)
-- Dependencies: 219
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
8a7f2c1e4d90
\.


--
-- TOC entry 4097 (class 0 OID 16758)
-- Dependencies: 245
-- Data for Name: apartado; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.apartado (id, usuario_id, cancelado_por_id, entregado_por_id, folio, cliente_nombre, cliente_telefono, estado, subtotal, total, total_abonado, saldo_pendiente, fecha_compromiso, observacion, liquidado_at, entregado_at, cancelado_at, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 4101 (class 0 OID 16836)
-- Dependencies: 249
-- Data for Name: apartado_abono; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.apartado_abono (id, apartado_id, usuario_id, monto, referencia, observacion, created_at, metodo_pago, monto_efectivo) FROM stdin;
\.


--
-- TOC entry 4099 (class 0 OID 16807)
-- Dependencies: 247
-- Data for Name: apartado_detalle; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.apartado_detalle (id, apartado_id, variante_id, cantidad, precio_unitario, subtotal_linea) FROM stdin;
\.


--
-- TOC entry 4073 (class 0 OID 16398)
-- Dependencies: 221
-- Data for Name: categoria; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.categoria (id, nombre, descripcion, activo, created_at, updated_at) FROM stdin;
1	Calzado	Calzado casual y deportivo.	t	2026-03-06 10:57:14.6721-06	2026-03-06 10:57:14.6721-06
2	Ropa	Ropa urbana y basicos.	t	2026-03-06 10:57:14.6721-06	2026-03-06 10:57:14.6721-06
\.


--
-- TOC entry 4087 (class 0 OID 16580)
-- Dependencies: 235
-- Data for Name: compra; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.compra (id, proveedor_id, usuario_id, numero_documento, estado, subtotal, total, observacion, confirmada_at, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 4091 (class 0 OID 16655)
-- Dependencies: 239
-- Data for Name: compra_detalle; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.compra_detalle (id, compra_id, variante_id, cantidad, costo_unitario, subtotal_linea) FROM stdin;
\.


--
-- TOC entry 4095 (class 0 OID 16714)
-- Dependencies: 243
-- Data for Name: configuracion_negocio; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.configuracion_negocio (id, nombre_negocio, telefono, direccion, pie_ticket, impresora_preferida, copias_ticket, created_at, updated_at, transferencia_banco, transferencia_beneficiario, transferencia_clabe, transferencia_instrucciones) FROM stdin;
1	POS System	\N	\N	Gracias por tu compra.	\N	1	2026-03-10 16:47:17.99791-06	2026-03-10 16:47:17.99791-06	\N	\N	\N	\N
\.


--
-- TOC entry 4075 (class 0 OID 16415)
-- Dependencies: 223
-- Data for Name: marca; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.marca (id, nombre, descripcion, activo, created_at, updated_at) FROM stdin;
1	Nike	\N	t	2026-03-06 10:57:14.6721-06	2026-03-06 10:57:14.6721-06
2	Levi's	\N	t	2026-03-06 10:57:14.6721-06	2026-03-06 10:57:14.6721-06
4	KSWISS	\N	t	2026-03-06 12:31:00.507378-06	2026-03-06 12:31:00.507378-06
5	Puma	\N	t	2026-03-06 13:37:49.329944-06	2026-03-06 13:37:49.329944-06
\.


--
-- TOC entry 4081 (class 0 OID 16504)
-- Dependencies: 229
-- Data for Name: movimiento_inventario; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.movimiento_inventario (id, variante_id, tipo_movimiento, cantidad, stock_anterior, stock_posterior, referencia, observacion, creado_por, created_at) FROM stdin;
1	1	ENTRADA_COMPRA	8	0	8	SEED-INITIAL	\N	SYSTEM	2026-03-06 10:57:14.6721-06
2	2	ENTRADA_COMPRA	5	0	5	SEED-INITIAL	\N	SYSTEM	2026-03-06 10:57:14.6721-06
3	3	ENTRADA_COMPRA	12	0	12	SEED-INITIAL	\N	SYSTEM	2026-03-06 10:57:14.6721-06
4	4	ENTRADA_COMPRA	9	0	9	SEED-INITIAL	\N	SYSTEM	2026-03-06 10:57:14.6721-06
5	3	AJUSTE_ENTRADA	1	12	13	ADJ-E121EE6B	\N	admin	2026-03-06 11:32:28.209882-06
6	1	AJUSTE_ENTRADA	1	8	9	ADJ-8EBEE976	\N	admin	2026-03-06 11:40:26.65086-06
7	1	AJUSTE_ENTRADA	1	9	10	ADJ-C86A630B	\N	admin	2026-03-06 11:40:33.705018-06
8	1	AJUSTE_ENTRADA	1	10	11	ADJ-CAF99459	\N	admin	2026-03-06 11:40:42.850167-06
9	4	AJUSTE_ENTRADA	1	9	10	ADJ-6B27A9D1	\N	admin	2026-03-06 12:09:51.934662-06
10	4	AJUSTE_ENTRADA	3	10	13	ADJ-250DA35F	\N	admin	2026-03-06 12:09:59.519811-06
11	6	AJUSTE_ENTRADA	2	0	2	ALTA-VARIANTE	Stock inicial al crear variante.	admin	2026-03-06 12:31:39.942549-06
12	1	AJUSTE_ENTRADA	7	11	18	ADJ-2AEC66ED	\N	admin	2026-03-06 13:03:54.19017-06
13	1	AJUSTE_ENTRADA	6	18	24	ADJ-2C2EC04E	\N	admin	2026-03-06 13:04:02.261812-06
14	1	AJUSTE_SALIDA	-18	24	6	ADJ-C11C1946	\N	admin	2026-03-06 13:08:25.387313-06
15	6	AJUSTE_ENTRADA	4	2	6	ADJ-4A77E92D	\N	admin	2026-03-06 13:14:01.700468-06
16	6	AJUSTE_SALIDA	-1	6	5	ADJ-05C75E18	\N	admin	2026-03-06 13:14:18.050462-06
17	6	AJUSTE_ENTRADA	1	5	6	ADJ-8B9DB2F8	\N	admin	2026-03-06 13:14:35.876224-06
18	4	AJUSTE_SALIDA	-8	13	5	ADJ-71A85C40	\N	admin	2026-03-06 13:28:01.617887-06
19	3	AJUSTE_SALIDA	-7	13	6	ADJ-21E02512	\N	admin	2026-03-06 13:28:13.684393-06
20	1	AJUSTE_SALIDA	-3	6	3	ADJ-F46D8145	\N	admin	2026-03-06 13:32:58.732181-06
21	6	AJUSTE_SALIDA	-6	6	0	ADJ-6D22B879	\N	admin	2026-03-06 13:34:05.297352-06
22	6	AJUSTE_ENTRADA	6	0	6	ADJ-28A49EBA	\N	admin	2026-03-06 13:34:51.567025-06
23	7	AJUSTE_ENTRADA	6	0	6	ALTA-VARIANTE	Stock inicial al crear variante.	admin	2026-03-06 13:38:53.519026-06
\.


--
-- TOC entry 4077 (class 0 OID 16432)
-- Dependencies: 225
-- Data for Name: producto; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.producto (id, categoria_id, marca_id, nombre, descripcion, activo, created_at, updated_at) FROM stdin;
1	1	1	Air Runner	Tenis ligeros para uso diario.	t	2026-03-06 10:57:14.6721-06	2026-03-06 12:41:14.35569-06
2	2	2	Jeans 511	Pantalon corte slim.	t	2026-03-06 10:57:14.6721-06	2026-03-06 13:29:02.453005-06
4	1	4	Tenis Concha	\N	t	2026-03-06 12:31:12.729729-06	2026-03-06 13:34:24.216912-06
5	1	5	Puma AIR	\N	t	2026-03-06 13:38:21.647009-06	2026-03-06 13:38:21.647009-06
\.


--
-- TOC entry 4083 (class 0 OID 16532)
-- Dependencies: 231
-- Data for Name: proveedor; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.proveedor (id, nombre, telefono, email, direccion, activo, created_at, updated_at) FROM stdin;
1	Proveedor Demo	555-0101	proveedor@example.com	\N	t	2026-03-06 10:57:14.6721-06	2026-03-06 10:57:14.6721-06
\.


--
-- TOC entry 4103 (class 0 OID 16864)
-- Dependencies: 251
-- Data for Name: sesion_caja; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sesion_caja (id, abierta_por_id, cerrada_por_id, monto_apertura, monto_cierre_declarado, monto_esperado_cierre, diferencia_cierre, observacion_apertura, observacion_cierre, abierta_at, cerrada_at) FROM stdin;
1	1	\N	100.00	\N	\N	\N	Prueba offscreen	\N	2026-03-10 18:11:22.009794-06	\N
\.


--
-- TOC entry 4085 (class 0 OID 16554)
-- Dependencies: 233
-- Data for Name: usuario; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.usuario (id, username, nombre_completo, password_hash, rol, activo, created_at, updated_at) FROM stdin;
2	cajero	Cajero General	pbkdf2_sha256$120000$63c7d4f2766087ee351d339a148a0ab6$4de1230aecf61adc4dcdf23233b75ed63370bc75bfb70e2cda7d1f87776a0f20	CAJERO	t	2026-03-06 10:57:14.6721-06	2026-03-06 11:03:56.234513-06
1	admin	Administrador Principal	pbkdf2_sha256$120000$36aaf306cbcc1492d5148ac4d709c632$140aa3863dae06fae83f449e75340242beb9b70d6f902a7feff6ca1c6861f33e	ADMIN	t	2026-03-06 10:57:14.6721-06	2026-03-10 16:42:09.568821-06
\.


--
-- TOC entry 4079 (class 0 OID 16463)
-- Dependencies: 227
-- Data for Name: variante; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.variante (id, producto_id, sku, talla, color, precio_venta, costo_referencia, stock_actual, activo, created_at, updated_at) FROM stdin;
2	2	NIK-AIR-RUN-WHT-27	27	Blanco	1499.00	980.00	5	t	2026-03-06 10:57:14.6721-06	2026-03-06 13:29:02.453005-06
4	2	LEV-511-BLK-34	34	Negro	899.00	550.00	5	t	2026-03-06 10:57:14.6721-06	2026-03-06 13:29:02.453005-06
1	1	NIK-AIR-RUN-BLK-26	26	Negro	1499.00	980.00	3	t	2026-03-06 10:57:14.6721-06	2026-03-06 13:32:58.732181-06
6	4	KSW-TENIS--BLAN-22	22	Blanco	1980.00	800.00	6	t	2026-03-06 12:31:39.942549-06	2026-03-06 13:34:51.567025-06
7	5	PUM-PUMA-A-BLAN-22	22	Blanco	1899.00	700.00	6	t	2026-03-06 13:38:53.519026-06	2026-03-06 14:27:34.17131-06
3	2	LEV-JEANS--AZUL-36	36	Azul	899.00	550.00	6	t	2026-03-06 10:57:14.6721-06	2026-03-10 19:07:03.947437-06
\.


--
-- TOC entry 4089 (class 0 OID 16622)
-- Dependencies: 237
-- Data for Name: venta; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.venta (id, usuario_id, cancelado_por_id, folio, estado, subtotal, total, observacion, confirmada_at, cancelada_at, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 4093 (class 0 OID 16684)
-- Dependencies: 241
-- Data for Name: venta_detalle; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.venta_detalle (id, venta_id, variante_id, cantidad, precio_unitario, subtotal_linea) FROM stdin;
\.


--
-- TOC entry 4125 (class 0 OID 0)
-- Dependencies: 248
-- Name: apartado_abono_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.apartado_abono_id_seq', 4, true);


--
-- TOC entry 4126 (class 0 OID 0)
-- Dependencies: 246
-- Name: apartado_detalle_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.apartado_detalle_id_seq', 4, true);


--
-- TOC entry 4127 (class 0 OID 0)
-- Dependencies: 244
-- Name: apartado_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.apartado_id_seq', 3, true);


--
-- TOC entry 4128 (class 0 OID 0)
-- Dependencies: 220
-- Name: categoria_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.categoria_id_seq', 3, true);


--
-- TOC entry 4129 (class 0 OID 0)
-- Dependencies: 238
-- Name: compra_detalle_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.compra_detalle_id_seq', 1, false);


--
-- TOC entry 4130 (class 0 OID 0)
-- Dependencies: 234
-- Name: compra_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.compra_id_seq', 1, false);


--
-- TOC entry 4131 (class 0 OID 0)
-- Dependencies: 242
-- Name: configuracion_negocio_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.configuracion_negocio_id_seq', 1, false);


--
-- TOC entry 4132 (class 0 OID 0)
-- Dependencies: 222
-- Name: marca_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.marca_id_seq', 5, true);


--
-- TOC entry 4133 (class 0 OID 0)
-- Dependencies: 228
-- Name: movimiento_inventario_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.movimiento_inventario_id_seq', 27, true);


--
-- TOC entry 4134 (class 0 OID 0)
-- Dependencies: 224
-- Name: producto_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.producto_id_seq', 5, true);


--
-- TOC entry 4135 (class 0 OID 0)
-- Dependencies: 230
-- Name: proveedor_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.proveedor_id_seq', 1, true);


--
-- TOC entry 4136 (class 0 OID 0)
-- Dependencies: 250
-- Name: sesion_caja_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.sesion_caja_id_seq', 1, true);


--
-- TOC entry 4137 (class 0 OID 0)
-- Dependencies: 232
-- Name: usuario_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.usuario_id_seq', 3, true);


--
-- TOC entry 4138 (class 0 OID 0)
-- Dependencies: 226
-- Name: variante_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.variante_id_seq', 7, true);


--
-- TOC entry 4139 (class 0 OID 0)
-- Dependencies: 240
-- Name: venta_detalle_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.venta_detalle_id_seq', 1, true);


--
-- TOC entry 4140 (class 0 OID 0)
-- Dependencies: 236
-- Name: venta_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.venta_id_seq', 1, true);


--
-- TOC entry 3820 (class 2606 OID 16396)
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- TOC entry 3888 (class 2606 OID 16822)
-- Name: apartado_detalle apartado_detalle_variante_unica; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_detalle
    ADD CONSTRAINT apartado_detalle_variante_unica UNIQUE (apartado_id, variante_id);


--
-- TOC entry 3864 (class 2606 OID 16670)
-- Name: compra_detalle compra_detalle_variante_unica; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra_detalle
    ADD CONSTRAINT compra_detalle_variante_unica UNIQUE (compra_id, variante_id);


--
-- TOC entry 3884 (class 2606 OID 16782)
-- Name: apartado pk_apartado; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado
    ADD CONSTRAINT pk_apartado PRIMARY KEY (id);


--
-- TOC entry 3896 (class 2606 OID 16850)
-- Name: apartado_abono pk_apartado_abono; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_abono
    ADD CONSTRAINT pk_apartado_abono PRIMARY KEY (id);


--
-- TOC entry 3892 (class 2606 OID 16820)
-- Name: apartado_detalle pk_apartado_detalle; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_detalle
    ADD CONSTRAINT pk_apartado_detalle PRIMARY KEY (id);


--
-- TOC entry 3823 (class 2606 OID 16412)
-- Name: categoria pk_categoria; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria
    ADD CONSTRAINT pk_categoria PRIMARY KEY (id);


--
-- TOC entry 3856 (class 2606 OID 16598)
-- Name: compra pk_compra; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra
    ADD CONSTRAINT pk_compra PRIMARY KEY (id);


--
-- TOC entry 3868 (class 2606 OID 16668)
-- Name: compra_detalle pk_compra_detalle; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra_detalle
    ADD CONSTRAINT pk_compra_detalle PRIMARY KEY (id);


--
-- TOC entry 3876 (class 2606 OID 16729)
-- Name: configuracion_negocio pk_configuracion_negocio; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracion_negocio
    ADD CONSTRAINT pk_configuracion_negocio PRIMARY KEY (id);


--
-- TOC entry 3826 (class 2606 OID 16429)
-- Name: marca pk_marca; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.marca
    ADD CONSTRAINT pk_marca PRIMARY KEY (id);


--
-- TOC entry 3843 (class 2606 OID 16522)
-- Name: movimiento_inventario pk_movimiento_inventario; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento_inventario
    ADD CONSTRAINT pk_movimiento_inventario PRIMARY KEY (id);


--
-- TOC entry 3829 (class 2606 OID 16448)
-- Name: producto pk_producto; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto
    ADD CONSTRAINT pk_producto PRIMARY KEY (id);


--
-- TOC entry 3846 (class 2606 OID 16546)
-- Name: proveedor pk_proveedor; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proveedor
    ADD CONSTRAINT pk_proveedor PRIMARY KEY (id);


--
-- TOC entry 3902 (class 2606 OID 16876)
-- Name: sesion_caja pk_sesion_caja; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_caja
    ADD CONSTRAINT pk_sesion_caja PRIMARY KEY (id);


--
-- TOC entry 3850 (class 2606 OID 16569)
-- Name: usuario pk_usuario; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT pk_usuario PRIMARY KEY (id);


--
-- TOC entry 3836 (class 2606 OID 16481)
-- Name: variante pk_variante; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variante
    ADD CONSTRAINT pk_variante PRIMARY KEY (id);


--
-- TOC entry 3862 (class 2606 OID 16639)
-- Name: venta pk_venta; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta
    ADD CONSTRAINT pk_venta PRIMARY KEY (id);


--
-- TOC entry 3872 (class 2606 OID 16697)
-- Name: venta_detalle pk_venta_detalle; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta_detalle
    ADD CONSTRAINT pk_venta_detalle PRIMARY KEY (id);


--
-- TOC entry 3831 (class 2606 OID 16450)
-- Name: producto producto_nombre_marca_unico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto
    ADD CONSTRAINT producto_nombre_marca_unico UNIQUE (marca_id, nombre);


--
-- TOC entry 3838 (class 2606 OID 16483)
-- Name: variante producto_talla_color_unico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variante
    ADD CONSTRAINT producto_talla_color_unico UNIQUE (producto_id, talla, color);


--
-- TOC entry 3886 (class 2606 OID 16784)
-- Name: apartado uq_apartado_folio; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado
    ADD CONSTRAINT uq_apartado_folio UNIQUE (folio);


--
-- TOC entry 3874 (class 2606 OID 16699)
-- Name: venta_detalle venta_detalle_variante_unica; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta_detalle
    ADD CONSTRAINT venta_detalle_variante_unica UNIQUE (venta_id, variante_id);


--
-- TOC entry 3893 (class 1259 OID 16861)
-- Name: ix_apartado_abono_apartado_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_abono_apartado_id ON public.apartado_abono USING btree (apartado_id);


--
-- TOC entry 3894 (class 1259 OID 16862)
-- Name: ix_apartado_abono_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_abono_usuario_id ON public.apartado_abono USING btree (usuario_id);


--
-- TOC entry 3877 (class 1259 OID 16801)
-- Name: ix_apartado_cancelado_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_cancelado_por_id ON public.apartado USING btree (cancelado_por_id);


--
-- TOC entry 3878 (class 1259 OID 16803)
-- Name: ix_apartado_cliente_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_cliente_nombre ON public.apartado USING btree (cliente_nombre);


--
-- TOC entry 3889 (class 1259 OID 16833)
-- Name: ix_apartado_detalle_apartado_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_detalle_apartado_id ON public.apartado_detalle USING btree (apartado_id);


--
-- TOC entry 3890 (class 1259 OID 16834)
-- Name: ix_apartado_detalle_variante_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_detalle_variante_id ON public.apartado_detalle USING btree (variante_id);


--
-- TOC entry 3879 (class 1259 OID 16802)
-- Name: ix_apartado_entregado_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_entregado_por_id ON public.apartado USING btree (entregado_por_id);


--
-- TOC entry 3880 (class 1259 OID 16804)
-- Name: ix_apartado_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_estado ON public.apartado USING btree (estado);


--
-- TOC entry 3881 (class 1259 OID 16805)
-- Name: ix_apartado_folio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_folio ON public.apartado USING btree (folio);


--
-- TOC entry 3882 (class 1259 OID 16800)
-- Name: ix_apartado_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apartado_usuario_id ON public.apartado USING btree (usuario_id);


--
-- TOC entry 3821 (class 1259 OID 16413)
-- Name: ix_categoria_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_categoria_nombre ON public.categoria USING btree (nombre);


--
-- TOC entry 3865 (class 1259 OID 16681)
-- Name: ix_compra_detalle_compra_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compra_detalle_compra_id ON public.compra_detalle USING btree (compra_id);


--
-- TOC entry 3866 (class 1259 OID 16682)
-- Name: ix_compra_detalle_variante_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compra_detalle_variante_id ON public.compra_detalle USING btree (variante_id);


--
-- TOC entry 3851 (class 1259 OID 16609)
-- Name: ix_compra_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compra_estado ON public.compra USING btree (estado);


--
-- TOC entry 3852 (class 1259 OID 16610)
-- Name: ix_compra_numero_documento; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_compra_numero_documento ON public.compra USING btree (numero_documento);


--
-- TOC entry 3853 (class 1259 OID 16611)
-- Name: ix_compra_proveedor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compra_proveedor_id ON public.compra USING btree (proveedor_id);


--
-- TOC entry 3854 (class 1259 OID 16612)
-- Name: ix_compra_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compra_usuario_id ON public.compra USING btree (usuario_id);


--
-- TOC entry 3824 (class 1259 OID 16430)
-- Name: ix_marca_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_marca_nombre ON public.marca USING btree (nombre);


--
-- TOC entry 3839 (class 1259 OID 16528)
-- Name: ix_movimiento_inventario_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_movimiento_inventario_created_at ON public.movimiento_inventario USING btree (created_at);


--
-- TOC entry 3840 (class 1259 OID 16529)
-- Name: ix_movimiento_inventario_tipo_movimiento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_movimiento_inventario_tipo_movimiento ON public.movimiento_inventario USING btree (tipo_movimiento);


--
-- TOC entry 3841 (class 1259 OID 16530)
-- Name: ix_movimiento_inventario_variante_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_movimiento_inventario_variante_id ON public.movimiento_inventario USING btree (variante_id);


--
-- TOC entry 3827 (class 1259 OID 16461)
-- Name: ix_producto_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_producto_nombre ON public.producto USING btree (nombre);


--
-- TOC entry 3844 (class 1259 OID 16547)
-- Name: ix_proveedor_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_proveedor_nombre ON public.proveedor USING btree (nombre);


--
-- TOC entry 3897 (class 1259 OID 16887)
-- Name: ix_sesion_caja_abierta_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sesion_caja_abierta_at ON public.sesion_caja USING btree (abierta_at);


--
-- TOC entry 3898 (class 1259 OID 16888)
-- Name: ix_sesion_caja_abierta_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sesion_caja_abierta_por_id ON public.sesion_caja USING btree (abierta_por_id);


--
-- TOC entry 3899 (class 1259 OID 16889)
-- Name: ix_sesion_caja_cerrada_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sesion_caja_cerrada_at ON public.sesion_caja USING btree (cerrada_at);


--
-- TOC entry 3900 (class 1259 OID 16890)
-- Name: ix_sesion_caja_cerrada_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sesion_caja_cerrada_por_id ON public.sesion_caja USING btree (cerrada_por_id);


--
-- TOC entry 3847 (class 1259 OID 16570)
-- Name: ix_usuario_rol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuario_rol ON public.usuario USING btree (rol);


--
-- TOC entry 3848 (class 1259 OID 16571)
-- Name: ix_usuario_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_usuario_username ON public.usuario USING btree (username);


--
-- TOC entry 3832 (class 1259 OID 16489)
-- Name: ix_variante_color; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_variante_color ON public.variante USING btree (color);


--
-- TOC entry 3833 (class 1259 OID 16490)
-- Name: ix_variante_sku; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_variante_sku ON public.variante USING btree (sku);


--
-- TOC entry 3834 (class 1259 OID 16491)
-- Name: ix_variante_talla; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_variante_talla ON public.variante USING btree (talla);


--
-- TOC entry 3857 (class 1259 OID 16650)
-- Name: ix_venta_cancelado_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_venta_cancelado_por_id ON public.venta USING btree (cancelado_por_id);


--
-- TOC entry 3869 (class 1259 OID 16710)
-- Name: ix_venta_detalle_variante_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_venta_detalle_variante_id ON public.venta_detalle USING btree (variante_id);


--
-- TOC entry 3870 (class 1259 OID 16711)
-- Name: ix_venta_detalle_venta_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_venta_detalle_venta_id ON public.venta_detalle USING btree (venta_id);


--
-- TOC entry 3858 (class 1259 OID 16651)
-- Name: ix_venta_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_venta_estado ON public.venta USING btree (estado);


--
-- TOC entry 3859 (class 1259 OID 16652)
-- Name: ix_venta_folio; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_venta_folio ON public.venta USING btree (folio);


--
-- TOC entry 3860 (class 1259 OID 16653)
-- Name: ix_venta_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_venta_usuario_id ON public.venta USING btree (usuario_id);


--
-- TOC entry 3920 (class 2606 OID 16851)
-- Name: apartado_abono fk_apartado_abono_apartado_id_apartado; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_abono
    ADD CONSTRAINT fk_apartado_abono_apartado_id_apartado FOREIGN KEY (apartado_id) REFERENCES public.apartado(id) ON DELETE CASCADE;


--
-- TOC entry 3921 (class 2606 OID 16856)
-- Name: apartado_abono fk_apartado_abono_usuario_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_abono
    ADD CONSTRAINT fk_apartado_abono_usuario_id_usuario FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- TOC entry 3915 (class 2606 OID 16785)
-- Name: apartado fk_apartado_cancelado_por_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado
    ADD CONSTRAINT fk_apartado_cancelado_por_id_usuario FOREIGN KEY (cancelado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- TOC entry 3918 (class 2606 OID 16823)
-- Name: apartado_detalle fk_apartado_detalle_apartado_id_apartado; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_detalle
    ADD CONSTRAINT fk_apartado_detalle_apartado_id_apartado FOREIGN KEY (apartado_id) REFERENCES public.apartado(id) ON DELETE CASCADE;


--
-- TOC entry 3919 (class 2606 OID 16828)
-- Name: apartado_detalle fk_apartado_detalle_variante_id_variante; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado_detalle
    ADD CONSTRAINT fk_apartado_detalle_variante_id_variante FOREIGN KEY (variante_id) REFERENCES public.variante(id) ON DELETE RESTRICT;


--
-- TOC entry 3916 (class 2606 OID 16790)
-- Name: apartado fk_apartado_entregado_por_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado
    ADD CONSTRAINT fk_apartado_entregado_por_id_usuario FOREIGN KEY (entregado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- TOC entry 3917 (class 2606 OID 16795)
-- Name: apartado fk_apartado_usuario_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartado
    ADD CONSTRAINT fk_apartado_usuario_id_usuario FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- TOC entry 3911 (class 2606 OID 16671)
-- Name: compra_detalle fk_compra_detalle_compra_id_compra; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra_detalle
    ADD CONSTRAINT fk_compra_detalle_compra_id_compra FOREIGN KEY (compra_id) REFERENCES public.compra(id) ON DELETE CASCADE;


--
-- TOC entry 3912 (class 2606 OID 16676)
-- Name: compra_detalle fk_compra_detalle_variante_id_variante; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra_detalle
    ADD CONSTRAINT fk_compra_detalle_variante_id_variante FOREIGN KEY (variante_id) REFERENCES public.variante(id) ON DELETE RESTRICT;


--
-- TOC entry 3907 (class 2606 OID 16599)
-- Name: compra fk_compra_proveedor_id_proveedor; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra
    ADD CONSTRAINT fk_compra_proveedor_id_proveedor FOREIGN KEY (proveedor_id) REFERENCES public.proveedor(id) ON DELETE RESTRICT;


--
-- TOC entry 3908 (class 2606 OID 16604)
-- Name: compra fk_compra_usuario_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compra
    ADD CONSTRAINT fk_compra_usuario_id_usuario FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- TOC entry 3906 (class 2606 OID 16523)
-- Name: movimiento_inventario fk_movimiento_inventario_variante_id_variante; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento_inventario
    ADD CONSTRAINT fk_movimiento_inventario_variante_id_variante FOREIGN KEY (variante_id) REFERENCES public.variante(id) ON DELETE RESTRICT;


--
-- TOC entry 3903 (class 2606 OID 16451)
-- Name: producto fk_producto_categoria_id_categoria; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto
    ADD CONSTRAINT fk_producto_categoria_id_categoria FOREIGN KEY (categoria_id) REFERENCES public.categoria(id) ON DELETE RESTRICT;


--
-- TOC entry 3904 (class 2606 OID 16456)
-- Name: producto fk_producto_marca_id_marca; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto
    ADD CONSTRAINT fk_producto_marca_id_marca FOREIGN KEY (marca_id) REFERENCES public.marca(id) ON DELETE RESTRICT;


--
-- TOC entry 3922 (class 2606 OID 16877)
-- Name: sesion_caja fk_sesion_caja_abierta_por_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_caja
    ADD CONSTRAINT fk_sesion_caja_abierta_por_id_usuario FOREIGN KEY (abierta_por_id) REFERENCES public.usuario(id);


--
-- TOC entry 3923 (class 2606 OID 16882)
-- Name: sesion_caja fk_sesion_caja_cerrada_por_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesion_caja
    ADD CONSTRAINT fk_sesion_caja_cerrada_por_id_usuario FOREIGN KEY (cerrada_por_id) REFERENCES public.usuario(id);


--
-- TOC entry 3905 (class 2606 OID 16484)
-- Name: variante fk_variante_producto_id_producto; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variante
    ADD CONSTRAINT fk_variante_producto_id_producto FOREIGN KEY (producto_id) REFERENCES public.producto(id) ON DELETE CASCADE;


--
-- TOC entry 3909 (class 2606 OID 16640)
-- Name: venta fk_venta_cancelado_por_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta
    ADD CONSTRAINT fk_venta_cancelado_por_id_usuario FOREIGN KEY (cancelado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- TOC entry 3913 (class 2606 OID 16700)
-- Name: venta_detalle fk_venta_detalle_variante_id_variante; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta_detalle
    ADD CONSTRAINT fk_venta_detalle_variante_id_variante FOREIGN KEY (variante_id) REFERENCES public.variante(id) ON DELETE RESTRICT;


--
-- TOC entry 3914 (class 2606 OID 16705)
-- Name: venta_detalle fk_venta_detalle_venta_id_venta; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta_detalle
    ADD CONSTRAINT fk_venta_detalle_venta_id_venta FOREIGN KEY (venta_id) REFERENCES public.venta(id) ON DELETE CASCADE;


--
-- TOC entry 3910 (class 2606 OID 16645)
-- Name: venta fk_venta_usuario_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venta
    ADD CONSTRAINT fk_venta_usuario_id_usuario FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


-- Completed on 2026-03-10 19:20:24 CST

--
-- PostgreSQL database dump complete
--

\unrestrict EpZiEx89NdLyIxLnvg1r0iLJNUH6JkUrKUZS0KzEUBCCjFtaBUR6MsVGo5wK3jM

