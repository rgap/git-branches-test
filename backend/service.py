import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import json
import os
import io
from dotenv import load_dotenv
import re

load_dotenv() 

# --- Configuración de la API de Gemini ---
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("La variable de entorno GEMINI_API_KEY no está configurada. Por favor, configúrala antes de ejecutar el servicio.")
    genai.configure(api_key=api_key)
except Exception as e:
    raise RuntimeError(f"Error al configurar la API de Gemini: {e}. Asegúrate de que GEMINI_API_KEY esté configurada correctamente.")

# --- Inicialización de la aplicación FastAPI ---
app = FastAPI(
    title="API de Análisis de Dataset con Gemini",
    description="Servicio de IA para análisis de datasets, proporcionando métricas, observaciones y sugerencias accionables.",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class Observacion(BaseModel):
    tipo_de_reporte: str
    titulo: str
    mensaje: str

class Sugerencia(BaseModel):
    tipo_de_reporte: str
    titulo: str
    mensaje: str

class Metricas(BaseModel):
    porcentaje_valores_faltantes: int
    porcentaje_filas_duplicadas: int 
    salud_del_dataset: int 

class ValidatedAnalysisResult(BaseModel):
    observaciones: list[Observacion]
    metricas: Metricas
    sugerencias: list[Sugerencia] 

# --- limpiar claves del JSON ---
def clean_json_keys(obj):
    if isinstance(obj, dict):
        return {
            k.strip().replace('\n', '').replace('"', '').replace("'", ''): clean_json_keys(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [clean_json_keys(item) for item in obj]
    return obj


# --- Endpoint ---
@app.post("/analyze_dataset/", response_model=ValidatedAnalysisResult)
async def analyze_dataset(file: UploadFile = File(...)):
    """
    Analiza un dataset CSV o Excel usando la IA de Gemini.
    Retorna métricas, observaciones y sugerencias en formato JSON.

    Args:
        file (UploadFile): El archivo del dataset (CSV) a analizar.

    Returns:
        AnalysisResult: Un objeto JSON con observaciones, métricas y sugerencias.

    Raises:
        HTTPException: Si el tipo de archivo no es soportado, el archivo está vacío,
                       o si ocurre un error durante el procesamiento o la comunicación con Gemini.
    """
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(status_code=400, detail="Tipo de archivo no soportado. Por favor, sube un archivo .csv o .xlsx")

    try:
        contents = await file.read()
        
        if file.filename.endswith('.csv'):
            try:
                df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
            except UnicodeDecodeError:
                df = pd.read_csv(io.StringIO(contents.decode('latin1')))
        elif file.filename.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(contents))
        
        dataset_string = df.to_csv(index=False)

        analysis_prompt_template = """
        Eres un servicio de IA Gemini altamente especializado en el análisis de datasets. Tu objetivo es analizar el dataset suministrado, proporcionar métricas, observaciones y sugerencias accionables para ofrecer un panorama completo sobre la estructura, patrones, anomalías y sesgos del dataset, guiando al usuario en su interpretación y en futuras acciones.

        Conceptos a detectar:
        1. Características:
            - Estructura:
                - Dimensión del dataset (nº de filas y columnas)
            - Patrón de variables:
                - Correlación Positiva/Negativa
                - Tendencias temporales
                - General (comportamiento general de las variables)
                - Estación (estacionalidad en datos temporales)
                - Clustering (agrupaciones naturales)
                - Asociación (reglas de asociación)
            - Anomalías de datos:
                - Valores atípicos (outliers)
                - Valores faltantes (NaN/null)
                - Inconsistencia
                - Mal formato
                - Duplicados
            - Distribución:
                - Importancia de características

        2. Sesgos:
            - Sesgos de datos:
                - Histórico
                - Representación
                - Medida
            - Sesgos de estructura:
                - Asociación
                - Confirmación (complaciente)
            - Sesgos de instrucción:
                - Contexto de Instrucción

        3. Tipos de observaciones decision making:
            - Data-Driven
            - Hypothesis-Driven
            - Exploratory-Driven

        Restricciones:
        - No infieras información de fuentes externas o no proporcionadas en el dataset.
        - No realices imputación automática de valores faltantes (NaN/null). Solo identifícalos y sugiere acciones.
        - No elimines automáticamente valores atípicos (outliers). Solo detéctalos y señala su impacto potencial.
        - No corrijas automáticamente inconsistencias o datos mal formateados. Reporta los hallazgos y sugiere correcciones manuales.
        - No elimines filas duplicadas automáticamente. Informa sobre su presencia y deja la decisión al usuario.
        - Al identificar correlaciones, 'correlación no implica causalidad'.
        - No intentes 'corregir' sesgos detectados en los datos; en su lugar, ofrece estrategias de mitigación para que el usuario las implemente.
        - Mantén un tono neutral y objetivo al reportar sobre sesgos, especialmente en datos sensibles; evita juicios de valor.
        - Todas las sugerencias y observaciones deben estar directamente respaldadas por la evidencia encontrada en el dataset analizado y debe entenderse facilmente para el usuario.
        - Las sugerencias deben ser accionables y específicas, evitando recomendaciones vagas o genéricas.
        - Reconoce explícitamente la limitación del servicio al no tener conocimiento intrínseco del contexto de negocio del usuario.
        - La salida debe ser clara, concisa y fácil de entender, priorizando la visualización sobre la jerga técnica excesiva.
        - No inventes información.
        - No des opiniones.
        - Arrays vacíos deben ser [].
        - No uses saltos de línea innecesarios dentro del JSON.
        - Responde SOLO con el JSON, sin texto adicional.
        - El análisis debe generar un máximo de 4 'sugerencias'.
        - Cada 'sugerencia' debe tener un límite de 100 caracteres.
        - Cada 'observacion' debe tener un límite de 100 caracteres.
        - No exceder el límite de entrega de 10 observaciones (Priorizar las más relevantes del análisis).
        - Las 'metricas' deben ser exclusivamente un valor numérico entre 0 y 100.
        - No hacer observaciones sobre los nombres de las columnas.
        - No hacer observaciones sobre los formatos de datos de las columnas.

        Formato de Salida Requerido:
        - Las claves principales de la salida JSON deben ser "observaciones", "metricas" y "sugerencias".
        - El contenido de "observaciones" contiene un límite de 100 caracteres y debe plantear el contenido de manera natural, legible y de fácil entendimiento para el usuario.
        - Las "observaciones" deben describir un porqué de la observación realizada, explicando su impacto o implicación. Deben usar los 'Conceptos a detectar' y 'Sesgos' para categorizar y dar contexto.
        - La estructura para cada elemento dentro de "observaciones" debe ser la siguiente:
        ```json
        {{
            "tipo_de_reporte": "string",
            "titulo": "string",
            "mensaje": "string"
        }}
        ```
        - Las 'metricas' deben ser exclusivamente un valor numérico entre 0 y 100.
        - La estructura para cada elemento dentro de "sugerencias" debe ser la siguiente:
        ```json
        {{
            "tipo_de_reporte": "string",
            "titulo": "string",
            "mensaje": "string"
        }}
        ```
        - Responde SOLO con el JSON, sin texto adicional.
        - Las "observaciones" deben describir un porqué de la observación realizada, explicando su impacto o implicación. Deben usar los 'Conceptos a detectar' y 'Sesgos' para categorizar y dar contexto.
        - Las "sugerencias" deben describir un porqué de la observación realizada, explicando su impacto o implicación. Deben usar los 'Conceptos a detectar' y 'Sesgos' para categorizar y dar contexto.
        - El formato del JSON DEBE ser el siguiente:
        ```json
        {{
            "observaciones": [
                {{"tipo_de_reporte": "observacion", "titulo": "string"}},
                {{"tipo_de_reporte": "observacion", "titulo": "string"}},
                {{"tipo_de_reporte": "observacion", "titulo": "string"}},
                {{"tipo_de_reporte": "observacion", "titulo": "string"}},
                {{"tipo_de_reporte": "observacion", "titulo": "string"}},
                {{"tipo_de_reporte": "observacion", "titulo": "string"}}
                // ... (hasta 10 objetos de observación, priorizando las más relevantes y con el porqué/impacto)
            ],
            "metricas": {{
                "porcentaje_valores_faltantes": int, // Ejemplo: 15
                "porcentaje_filas_duplicadas": int, // Ejemplo: 5
                "salud_del_dataset": int // Ejemplo: 75
            }},
            "sugerencias": [
                {{"tipo_de_reporte": "sugerencia", "titulo": "string"}},
                {{"tipo_de_reporte": "sugerencia", "titulo": "string"}},
                {{"tipo_de_reporte": "sugerencia", "titulo": "string"}},
                {{"tipo_de_reporte": "sugerencia", "titulo": "string"}}
                // ... (hasta 4 objetos de sugerencia, accionables y específicas)
            ]
        }}
        ```
        Dataset a analizar (en formato CSV):
        ```csv
        {dataset_content}
        ```
        """
        
        formatted_prompt = analysis_prompt_template.format(dataset_content=dataset_string)
        
        # --- Depuración ---
        print(f"DEBUG: Prompt formateado (primeros 500 caracteres): {formatted_prompt[:500]}...")
        print(f"DEBUG: Longitud total del prompt: {len(formatted_prompt)} caracteres.")

        model = genai.GenerativeModel('gemini-2.0-flash')

        response = None 
        try:
            print("DEBUG: Intentando llamar a model.generate_content()...")
            response = model.generate_content(
                formatted_prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            print(f"DEBUG: Llamada a model.generate_content() completada. Objeto de respuesta: {response}")
            
            if not hasattr(response, 'text') or not response.text:
                print(f"ADVERTENCIA: La respuesta de Gemini no tiene atributo 'text' o está vacía. Objeto completo: {response}")
                if response.candidates and response.candidates[0].finish_reason:
                    reason = response.candidates[0].finish_reason
                    raise ValueError(f"Gemini API no retornó texto. Razón de finalización: {reason}. Objeto completo: {response}")
                else:
                    raise ValueError(f"Gemini API no retornó texto. Objeto completo: {response}")

            raw_gemini_response = response.text
            print(f"DEBUG: Respuesta cruda de Gemini (para depuración): {raw_gemini_response[:1000]}")

        except Exception as gemini_api_call_e:
            print(f"ERROR: Fallo en la llamada a Gemini API: {gemini_api_call_e}")
            print(f"ERROR: Tipo de excepción de la llamada a Gemini: {type(gemini_api_call_e)}")
            print(f"ERROR: Representación completa de la excepción: {repr(gemini_api_call_e)}")
            raise HTTPException(status_code=500, detail=f"Error en la comunicación con Gemini API: {gemini_api_call_e}")

        try:
            json_match = re.search(r'\{.*\}', raw_gemini_response, re.DOTALL | re.MULTILINE)

            if not json_match:
                print(f"ERROR: No se encontró bloque JSON en la respuesta. Respuesta completa de Gemini: {raw_gemini_response}")
                raise ValueError("No se encontró un bloque JSON válido en la respuesta de Gemini.")

            json_str = json_match.group(0)
            parsed_json = json.loads(json_str)
            cleaned_json = clean_json_keys(parsed_json)

            print("DEBUG: JSON limpio final:")
            print(json.dumps(cleaned_json, indent=2, ensure_ascii=False))

            try:
                validated = ValidatedAnalysisResult(**cleaned_json)
            except Exception as validation_error:
                print(f"ERROR: Validación fallida del JSON con Pydantic: {validation_error}")
                raise HTTPException(status_code=500, detail="El JSON recibido no cumple con la estructura esperada.")

            return validated

        except (json.JSONDecodeError, ValueError) as e:
            print(f"ERROR: Fallo al procesar la respuesta JSON de Gemini: {e}")
            print(f"ERROR: Tipo de excepción de parseo JSON: {type(e)}")
            print(f"ERROR: Respuesta cruda de Gemini (en excepción de parseo): {raw_gemini_response}")
            raise HTTPException(status_code=500, detail=f"Error al procesar la respuesta de Gemini: {e}. Respuesta recibida: {raw_gemini_response[:500]}...")

    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="El archivo está vacío o no contiene datos.")
    except Exception as e:
        print(f"ERROR: Error inesperado en analyze_dataset (catch-all final): {e}")
        print(f"ERROR: Tipo de excepción inesperada (catch-all final): {type(e)}")
        print(f"ERROR: Representación completa de la excepción (catch-all final): {repr(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service", host="0.0.0.0", port=8000, reload=True)
