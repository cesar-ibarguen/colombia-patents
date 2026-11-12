"""
patentes_a_sql.py
=================
Convierte el CSV plano de patentes presentadas en Colombia (SIC, 2000-2021)
en una base de datos relacional normalizada para MySQL, y genera un informe
de calidad de datos.

Uso:
    python patentes_a_sql.py Patentes_presentadas.csv patentes.sql

Salidas:
    patentes.sql          CREATE DATABASE + tablas + INSERT (listo para SOURCE)
    calidad_datos.md      informe de los problemas encontrados y cómo se trataron

Modelo (tercera forma normal):

    pais (pais_id, nombre)
    sector (sector_id, nombre)
    naturaleza (naturaleza_id, nombre, tramite, via)
    solicitud (solicitud_id, fecha, naturaleza_id, sector_id, pais_id,
               region, ciudad, residente)
    solicitante (solicitante_id, nombre, pais_codigo)
    inventor (inventor_id, nombre)
    solicitud_solicitante (solicitud_id, solicitante_id, orden)   -- N:M
    solicitud_inventor   (solicitud_id, inventor_id, orden)       -- N:M
"""

import re
import sys

import pandas as pd

BASE = "patentes"
FILAS_POR_INSERT = 1000
informe = []          # líneas del informe de calidad


def nota(texto):
    informe.append(texto)


# ----------------------------------------------------------------------
# 1. LECTURA
# ----------------------------------------------------------------------
def leer(ruta):
    # dtype=str: leemos todo como texto y convertimos nosotros, con control
    df = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str)
    df.columns = ["solicitud_id", "anio", "naturaleza", "sector", "fecha",
                  "pais_id", "region", "ciudad", "solicitante", "inventor",
                  "residente", "tramite", "pais_nombre", "via"]
    for c in df.columns:
        df[c] = df[c].str.strip()
    nota(f"- Filas leídas: **{len(df):,}**; columnas: {len(df.columns)}.")
    return df


# ----------------------------------------------------------------------
# 2. LIMPIEZA Y VALIDACIONES de la tabla plana
# ----------------------------------------------------------------------
def limpiar(df):
    # Fecha dd/mm/aaaa -> DATE
    df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y")
    # Año: viene como texto con separador de miles ("2,017")
    anio = df["anio"].str.replace(",", "", regex=False).astype(int)
    distintos = (anio != df["fecha"].dt.year).sum()
    nota(f"- `Año Presentación` venía como texto con coma de miles (`\"2,017\"`). "
         f"Se comparó con el año de la fecha: **{distintos}** diferencias, así que "
         f"es redundante y no se guarda (se obtiene con `YEAR(fecha)`).")
    df = df.drop(columns="anio")

    # Región: dos formas de decir "sin dato"
    nd = (df["region"] == "NOT DEFINED").sum()
    vacias = df["region"].isna().sum()
    df["region"] = df["region"].replace("NOT DEFINED", None)
    nota(f"- `Region` tenía {vacias:,} vacíos y {nd:,} valores `NOT DEFINED`; "
         f"ambos se unificaron como `NULL`.")

    # Residente -> booleano, y verificación contra el país
    df["residente"] = (df["residente"] == "Residente").astype(int)
    raros = df[(df["residente"] == 1) & (df["pais_id"] != "CO")]
    nota(f"- `Residente` se convirtió a booleano. Anomalía: **{len(raros)}** "
         f"solicitud(es) marcada(s) como residente con país distinto de Colombia "
         f"({', '.join(raros['solicitud_id'] + ' → ' + raros['pais_id'])}). "
         f"Se conserva el dato original.")

    sin_sector = df["sector"].isna().sum()
    nota(f"- `Sector` vacío en {sin_sector} solicitudes: quedan como `NULL`.")
    return df


# ----------------------------------------------------------------------
# 3. TABLAS DE CATÁLOGO
# ----------------------------------------------------------------------
def catalogos(df):
    # País: el código determina el nombre (se verifica)
    assert (df.groupby("pais_id")["pais_nombre"].nunique() == 1).all()
    pais = (df[["pais_id", "pais_nombre"]].drop_duplicates()
            .rename(columns={"pais_nombre": "nombre"}).sort_values("pais_id"))

    sector = (df["sector"].dropna().drop_duplicates().sort_values()
              .reset_index(drop=True).to_frame("nombre"))
    sector.insert(0, "sector_id", range(1, len(sector) + 1))

    # Naturaleza determina Trámite y Vía -> dependencia funcional -> catálogo
    assert (df.groupby("naturaleza")[["tramite", "via"]].nunique() == 1).all().all()
    naturaleza = (df[["naturaleza", "tramite", "via"]].drop_duplicates()
                  .sort_values("naturaleza").reset_index(drop=True)
                  .rename(columns={"naturaleza": "nombre"}))
    naturaleza.insert(0, "naturaleza_id", range(1, len(naturaleza) + 1))
    nota("- `Naturaleza` determina por completo `Trámite` y `Vía` (dependencia "
         "funcional verificada), por eso las tres pasan a la tabla `naturaleza` "
         "y `solicitud` solo guarda `naturaleza_id` (3FN).")
    nota("- `Pais`/`Pais Nombre`: el código determina el nombre; se guardan una vez "
         "en la tabla `pais`.")
    return pais, sector, naturaleza


# ----------------------------------------------------------------------
# 4. RELACIONES MUCHOS A MUCHOS (celdas con varios valores separados por ;)
# ----------------------------------------------------------------------
PATRON_PAIS = re.compile(r"\s*\(([A-Z]{2})?\)\s*$")


def separar(df, columna):
    """Una fila por (solicitud, valor), conservando el orden y sin repetidos."""
    t = df[["solicitud_id", columna]].dropna().copy()
    t[columna] = t[columna].str.split(";")
    t = t.explode(columna).reset_index(drop=True)   # índice único tras explode
    t[columna] = t[columna].str.strip().str.replace(r"\s+", " ", regex=True)
    t = t[t[columna] != ""]
    antes = len(t)
    t = t.drop_duplicates(["solicitud_id", columna]).reset_index(drop=True)
    t["orden"] = t.groupby("solicitud_id").cumcount() + 1
    return t, antes - len(t)


def relaciones(df):
    # --- Solicitantes: "NOMBRE (XX)" -> nombre + código de país
    s, rep_s = separar(df, "solicitante")
    cod = s["solicitante"].str.extract(PATRON_PAIS)[0]
    s["pais_codigo"] = cod
    s["nombre"] = s["solicitante"].str.replace(PATRON_PAIS, "", regex=True).str.strip()
    multi = (df["solicitante"].str.count(";") > 0).sum()
    nota(f"- `Solicitante`: {multi:,} solicitudes tienen varios solicitantes "
         f"separados por `;`. Se separaron en la tabla puente `solicitud_solicitante`.")
    nota(f"- El código de país del solicitante venía dentro del nombre, "
         f"`EMPRESA (US)`; se extrajo a `pais_codigo`. **{cod.isna().sum():,}** "
         f"menciones no traen código (o traen `()` vacío).")
    sol = (s[["nombre", "pais_codigo"]].drop_duplicates()
           .sort_values(["nombre", "pais_codigo"], na_position="first")
           .reset_index(drop=True))
    sol.insert(0, "solicitante_id", range(1, len(sol) + 1))
    s = s.merge(sol, on=["nombre", "pais_codigo"], how="left")
    sol_sol = s[["solicitud_id", "solicitante_id", "orden"]]

    # Variantes de escritura (no se fusionan: se documentan)
    ejemplo = sol[sol["nombre"].str.startswith("BAYER CROPSCIENCE")]["nombre"].tolist()
    nota(f"- Una misma empresa aparece escrita de varias formas, por ejemplo: "
         + "; ".join(f"`{x}`" for x in ejemplo[:5])
         + ". **No se fusionaron automáticamente** para no unir entidades distintas "
           "por error. Para análisis por empresa conviene agrupar con `LIKE` o "
           "crear una tabla de equivalencias.")

    # --- Inventores
    i, rep_i = separar(df, "inventor")
    inv = i[["inventor"]].drop_duplicates().sort_values("inventor").reset_index(drop=True)
    inv.insert(0, "inventor_id", range(1, len(inv) + 1))
    inv = inv.rename(columns={"inventor": "nombre"})
    i = i.merge(inv, left_on="inventor", right_on="nombre")
    sol_inv = i[["solicitud_id", "inventor_id", "orden"]]
    multi_i = (df["inventor"].str.count(";") > 0).sum()
    max_i = df["inventor"].dropna().str.count(";").max() + 1
    nota(f"- `Inventor`: {multi_i:,} solicitudes ({multi_i/len(df):.0%}) tienen "
         f"varios inventores (máximo {max_i}). Se separaron en `solicitud_inventor`. "
         f"Se eliminaron {rep_i} repeticiones del mismo inventor en una misma "
         f"solicitud y {rep_s} de solicitantes. {df['inventor'].isna().sum()} "
         f"solicitudes no tienen inventor.")
    nota("- Limitación: dos inventores con el mismo nombre se consideran la misma "
         "persona (el archivo no trae un identificador de inventor).")
    return sol, sol_sol, inv, sol_inv


# ----------------------------------------------------------------------
# 5. GENERACIÓN DEL SQL
# ----------------------------------------------------------------------
DDL = """
CREATE TABLE pais (
    pais_id   CHAR(2)      PRIMARY KEY,
    nombre    VARCHAR(80)  NOT NULL
);
CREATE TABLE sector (
    sector_id INT          PRIMARY KEY,
    nombre    VARCHAR(40)  NOT NULL UNIQUE
);
CREATE TABLE naturaleza (
    naturaleza_id INT          PRIMARY KEY,
    nombre        VARCHAR(60)  NOT NULL UNIQUE,
    tramite       VARCHAR(40)  NOT NULL,
    via           VARCHAR(10)  NOT NULL      -- 'PCT' o 'Nacional'
);
CREATE TABLE solicitud (
    solicitud_id  VARCHAR(12)  PRIMARY KEY,
    fecha         DATE         NOT NULL,
    naturaleza_id INT          NOT NULL,
    sector_id     INT          NULL,
    pais_id       CHAR(2)      NOT NULL,     -- país del primer solicitante
    region        VARCHAR(80)  NULL,
    ciudad        VARCHAR(80)  NULL,
    residente     BOOLEAN      NOT NULL,     -- 1 = solicitante residente en Colombia
    FOREIGN KEY (naturaleza_id) REFERENCES naturaleza(naturaleza_id),
    FOREIGN KEY (sector_id)     REFERENCES sector(sector_id),
    FOREIGN KEY (pais_id)       REFERENCES pais(pais_id),
    INDEX idx_fecha (fecha)
);
CREATE TABLE solicitante (
    solicitante_id INT          PRIMARY KEY,
    nombre         VARCHAR(255) NOT NULL,
    pais_codigo    CHAR(2)      NULL         -- tomado del nombre; puede no estar en `pais`
);
CREATE TABLE inventor (
    inventor_id INT          PRIMARY KEY,
    nombre      VARCHAR(150) NOT NULL
);
CREATE TABLE solicitud_solicitante (
    solicitud_id   VARCHAR(12) NOT NULL,
    solicitante_id INT         NOT NULL,
    orden          TINYINT     NOT NULL,     -- 1 = solicitante principal
    PRIMARY KEY (solicitud_id, solicitante_id),
    FOREIGN KEY (solicitud_id)   REFERENCES solicitud(solicitud_id),
    FOREIGN KEY (solicitante_id) REFERENCES solicitante(solicitante_id)
);
CREATE TABLE solicitud_inventor (
    solicitud_id VARCHAR(12) NOT NULL,
    inventor_id  INT         NOT NULL,
    orden        SMALLINT    NOT NULL,
    PRIMARY KEY (solicitud_id, inventor_id),
    FOREIGN KEY (solicitud_id) REFERENCES solicitud(solicitud_id),
    FOREIGN KEY (inventor_id)  REFERENCES inventor(inventor_id)
);
"""


def literal(serie):
    if pd.api.types.is_datetime64_any_dtype(serie):
        txt = "'" + serie.dt.strftime("%Y-%m-%d") + "'"
    elif pd.api.types.is_numeric_dtype(serie):
        txt = serie.astype("Int64").astype(str)
    else:
        txt = ("'" + serie.astype(str).str.replace("\\", "\\\\", regex=False)
               .str.replace("'", "''", regex=False) + "'")
    return txt.where(serie.notna(), "NULL")


def inserts(df, tabla):
    cols = ", ".join(df.columns)
    filas = "(" + pd.DataFrame({c: literal(df[c]) for c in df.columns}).agg(", ".join, axis=1) + ")"
    partes = [f"INSERT INTO {tabla} ({cols}) VALUES\n" + ",\n".join(filas.iloc[k:k + FILAS_POR_INSERT]) + ";\n"
              for k in range(0, len(filas), FILAS_POR_INSERT)]
    return f"-- {tabla}: {len(df):,} filas\nSTART TRANSACTION;\n" + "".join(partes) + "COMMIT;\n\n"


def main(entrada, salida):
    df = limpiar(leer(entrada))
    pais, sector, naturaleza = catalogos(df)
    sol, sol_sol, inv, sol_inv = relaciones(df)

    solicitud = (df.merge(naturaleza[["naturaleza_id", "nombre"]],
                          left_on="naturaleza", right_on="nombre")
                   .merge(sector.rename(columns={"nombre": "sector"}), on="sector", how="left"))
    solicitud = solicitud[["solicitud_id", "fecha", "naturaleza_id", "sector_id",
                           "pais_id", "region", "ciudad", "residente"]]
    solicitud["sector_id"] = solicitud["sector_id"].astype("Int64")

    tablas = [("pais", pais), ("sector", sector), ("naturaleza", naturaleza),
              ("solicitud", solicitud), ("solicitante", sol), ("inventor", inv),
              ("solicitud_solicitante", sol_sol), ("solicitud_inventor", sol_inv)]

    with open(salida, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"-- Patentes presentadas en Colombia 2000-2021 (SIC), modelo relacional\n"
                f"-- Generado con patentes_a_sql.py\n"
                f"DROP DATABASE IF EXISTS {BASE};\n"
                f"CREATE DATABASE {BASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
                f"USE {BASE};\n" + DDL + "\n")
        for nombre, t in tablas:
            f.write(inserts(t, nombre))

    resumen = "\n".join(f"| `{n}` | {len(t):,} |" for n, t in tablas)
    with open("calidad_datos.md", "w", encoding="utf-8") as f:
        f.write("# Informe de calidad de datos: patentes presentadas en Colombia\n\n"
                "Fuente: Superintendencia de Industria y Comercio (SIC), solicitudes "
                "de patente 2000-2021, archivo `Patentes_presentadas.csv`.\n\n"
                "## Hallazgos y tratamiento\n\n" + "\n".join(informe) +
                "\n\n## Tablas resultantes\n\n| Tabla | Filas |\n|---|---|\n" + resumen + "\n")
    for n, t in tablas:
        print(f"{n:<22} {len(t):>8,}")
    print(f"\nListo: {salida} y calidad_datos.md")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Patentes_presentadas.csv",
         sys.argv[2] if len(sys.argv) > 2 else "patentes.sql")
