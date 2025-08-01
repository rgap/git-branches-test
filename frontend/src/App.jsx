import axios from "axios";
import { useState } from "react";
import { useDropzone } from "react-dropzone";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const onDrop = acceptedFiles => {
    const selectedFile = acceptedFiles[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
      setAnalysis(null);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    },
    multiple: false,
  });

  const analyzeDataset = async () => {
    if (!file) {
      setError("Por favor selecciona un archivo");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API_BASE_URL}/analyze_dataset/`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        timeout: parseInt(import.meta.env.VITE_API_TIMEOUT) || 30000,
      });

      setAnalysis(response.data);
    } catch (err) {
      console.error("Error analyzing dataset:", err);
      setError(err.response?.data?.detail || "Error al analizar el dataset");
    } finally {
      setLoading(false);
    }
  };

  const resetAnalysis = () => {
    setFile(null);
    setAnalysis(null);
    setError(null);
  };

  return (
    <div className="container">
      <header className="header">
        <h1>🔬 Analizador de Datasets con IA</h1>
        <p>Sube tu archivo CSV o Excel para obtener análisis inteligente</p>
      </header>

      <main className="main">
        {!analysis ? (
          <div className="upload-section">
            <div {...getRootProps()} className={`dropzone ${isDragActive ? "active" : ""}`}>
              <input {...getInputProps()} />
              {file ? (
                <div className="file-selected">
                  <span>📄 {file.name}</span>
                  <small>({(file.size / 1024).toFixed(1)} KB)</small>
                </div>
              ) : (
                <div className="dropzone-content">
                  <div className="upload-icon">📊</div>
                  <p>{isDragActive ? "Suelta el archivo aquí..." : "Arrastra un archivo CSV/Excel aquí o haz clic para seleccionar"}</p>
                  <small>Formatos soportados: .csv, .xlsx</small>
                </div>
              )}
            </div>

            {file && (
              <div className="action-buttons">
                <button onClick={analyzeDataset} disabled={loading} className="analyze-btn">
                  {loading ? "⏳ Analizando..." : "🚀 Analizar Dataset"}
                </button>
                <button onClick={() => setFile(null)} className="clear-btn">
                  🗑️ Limpiar
                </button>
              </div>
            )}

            {error && (
              <div className="error">
                <strong>❌ Error:</strong> {error}
              </div>
            )}
          </div>
        ) : (
          <div className="results-section">
            <div className="results-header">
              <h2>📈 Resultados del Análisis</h2>
              <button onClick={resetAnalysis} className="new-analysis-btn">
                📁 Nuevo Análisis
              </button>
            </div>

            <div className="metrics-grid">
              <div className="metric-card">
                <h3>Valores Faltantes</h3>
                <div className="metric-value">{analysis.metricas.porcentaje_valores_faltantes}%</div>
              </div>
              <div className="metric-card">
                <h3>Filas Duplicadas</h3>
                <div className="metric-value">{analysis.metricas.porcentaje_filas_duplicadas}%</div>
              </div>
              <div className="metric-card">
                <h3>Salud del Dataset</h3>
                <div className="metric-value health">{analysis.metricas.salud_del_dataset}%</div>
              </div>
            </div>

            <div className="analysis-sections">
              <section className="observations">
                <h3>🔍 Observaciones</h3>
                {analysis.observaciones.length > 0 ? (
                  <div className="cards-grid">
                    {analysis.observaciones.map((obs, index) => (
                      <div key={index} className="analysis-card observation">
                        <h4>{obs.titulo}</h4>
                        <p>{obs.mensaje}</p>
                        <span className="card-type">{obs.tipo_de_reporte}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-data">No se encontraron observaciones relevantes.</p>
                )}
              </section>

              <section className="suggestions">
                <h3>💡 Sugerencias</h3>
                {analysis.sugerencias.length > 0 ? (
                  <div className="cards-grid">
                    {analysis.sugerencias.map((sug, index) => (
                      <div key={index} className="analysis-card suggestion">
                        <h4>{sug.titulo}</h4>
                        <p>{sug.mensaje}</p>
                        <span className="card-type">{sug.tipo_de_reporte}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-data">No hay sugerencias disponibles.</p>
                )}
              </section>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
