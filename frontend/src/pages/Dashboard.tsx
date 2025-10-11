import { useEffect, useState } from "react";
import axios from "axios";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

// Type Definitions
interface Reading {
  time: string;
  Temperature: number;
  Humidity: number;
  Battery: number;
  Motion?: number;
}

interface Analytics {
  avg_temperature: number;
  avg_humidity: number;
  avg_battery: number;
  recent_readings: Reading[];
}

interface Prediction {
  predicted_next_temperature: number | null;
}

interface Anomaly {
  time: string;
  Battery: number;
  Humidity: number;
  Motion?: number;
  Temperature: number;
}

function Dashboard() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, []);

  async function fetchAll() {
    if (!loading) setIsRefreshing(true);
    setError(null);
    try {
      console.log("Fetching from:", API_BASE);
      const [analyticsRes, anomaliesRes, predictionRes] = await Promise.all([
        axios.get<Analytics>(`${API_BASE}/analytics`, { timeout: 10000 }),
        axios.get<Anomaly[]>(`${API_BASE}/anomalies`, { timeout: 10000 }),
        axios.get<Prediction>(`${API_BASE}/predict`, { timeout: 10000 }),
      ]);
      console.log("Analytics response:", analyticsRes.data);
      setAnalytics(analyticsRes.data);
      setAnomalies(Array.isArray(anomaliesRes.data) ? anomaliesRes.data : []);
      setPrediction(predictionRes.data);
    } catch (e: any) {
      console.error("Fetch error:", e);
      if (e.code === "ERR_NETWORK") {
        setError(
          `Cannot connect to API at ${API_BASE}. Check if backend is running and CORS is enabled.`
        );
      } else if (e.response) {
        setError(`API error: ${e.response.status} - ${e.response.statusText}`);
      } else {
        setError(`Error: ${e.message}`);
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }

  const formatTime = (t: string) => {
    try {
      const d = new Date(t);
      return `${d.getHours().toString().padStart(2, "0")}:${d
        .getMinutes()
        .toString()
        .padStart(2, "0")}`;
    } catch {
      return t;
    }
  };

  // Error State Component
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl">
          <div className="bg-red-50 border-2 border-red-200 rounded-xl p-6 md:p-8 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-red-500 rounded-full flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <h2 className="text-xl md:text-2xl font-bold text-red-800">
                Connection Error
              </h2>
            </div>
            <p className="text-red-700 mb-6">{error}</p>
            <button
              onClick={fetchAll}
              className="bg-red-500 hover:bg-red-600 text-white px-6 py-3 rounded-lg font-semibold transition-colors shadow-md"
            >
              Retry Connection
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Main Dashboard Content
  return (
    <div className="min-h-screen bg-gray-100 p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-4 md:space-y-6">
        {/* Header Card */}
        <div className="bg-white rounded-2xl shadow-sm p-5 md:p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-2">
                <span className="text-blue-500">Smart Home </span>
                <span className="text-teal-400">Analytics</span>
              </h1>
              <p className="text-sm md:text-base text-gray-600">
                Real-time IoT sensor monitoring & prediction
              </p>
            </div>
            <button 
              onClick={fetchAll}
              disabled={loading || isRefreshing}
              className="bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 text-blue-500 px-6 py-3 rounded-lg font-semibold transition-colors flex items-center gap-2 shadow-sm w-full sm:w-auto justify-center"
            >
              <svg
                className={`w-5 h-5 ${isRefreshing ? "animate-spin" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              {loading ? "Loading..." : isRefreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-5">
          {/* Temperature Card */}
          <div className="bg-orange-50 rounded-2xl p-5 md:p-6 shadow-sm border border-orange-100">
            <div className="flex items-start justify-between mb-4">
              <h2 className="text-base md:text-lg font-bold text-gray-900">
                Avg Temperature
              </h2>
              <div className="w-10 h-10 bg-orange-200 rounded-xl flex items-center justify-center">
                <svg className="w-5 h-5 text-orange-600" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M13 2L3 14h8l-1 8 10-12h-8l1-8z"/>
                </svg>
              </div>
            </div>
            <p className="text-4xl md:text-5xl font-bold text-gray-900">
              {loading
                ? "..."
                : analytics
                ? `${analytics.avg_temperature.toFixed(2)} °C`
                : "N/A"}
            </p>
          </div>

          {/* Humidity Card */}
          <div className="bg-blue-50 rounded-2xl p-5 md:p-6 shadow-sm border border-blue-100">
            <div className="flex items-start justify-between mb-4">
              <h2 className="text-base md:text-lg font-bold text-gray-900">
                Avg Humidity
              </h2>
              <div className="w-10 h-10 bg-blue-200 rounded-xl flex items-center justify-center">
                <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                </svg>
              </div>
            </div>
            <p className="text-4xl md:text-5xl font-bold text-gray-900">
              {loading
                ? "..."
                : analytics
                ? `${analytics.avg_humidity.toFixed(2)} %`
                : "N/A"}
            </p>
          </div>

          {/* Battery Card */}
          <div className="bg-green-50 rounded-2xl p-5 md:p-6 shadow-sm border border-green-100">
            <div className="flex items-start justify-between mb-4">
              <h2 className="text-base md:text-lg font-bold text-gray-900">
                Avg Battery
              </h2>
              <div className="w-10 h-10 bg-green-200 rounded-xl flex items-center justify-center">
                <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <p className="text-4xl md:text-5xl font-bold text-gray-900">
              {loading
                ? "..."
                : analytics
                ? `${analytics.avg_battery.toFixed(2)} %`
                : "N/A"}
            </p>
          </div>
        </div>

        {/* Prediction Section */}
        <div className="bg-blue-50 rounded-2xl p-5 md:p-6 shadow-sm border border-blue-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-blue-200 rounded-xl flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 24 24">
                <path d="M13 2L3 14h8l-1 8 10-12h-8l1-8z"/>
              </svg>
            </div>
            <h2 className="text-xl md:text-2xl font-bold text-gray-900">
              AI Temperature Prediction
            </h2>
          </div>
          {loading ? (
            <p className="text-gray-500">Loading prediction...</p>
          ) : prediction?.predicted_next_temperature !== null &&
            prediction?.predicted_next_temperature !== undefined ? (
            <div className="flex items-baseline gap-3">
              <p className="text-5xl md:text-6xl font-bold text-blue-600">
                {prediction.predicted_next_temperature.toFixed(2)} °C
              </p>
              <span className="text-base md:text-lg text-gray-600">next reading</span>
            </div>
          ) : (
            <p className="text-gray-500">
              Prediction not ready - gathering data...
            </p>
          )}
        </div>

        {/* Chart Section */}
        {!loading && analytics?.recent_readings?.length ? (
          <div className="bg-white rounded-2xl p-5 md:p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                </svg>
              </div>
              <h2 className="text-xl md:text-2xl font-bold text-gray-900">
                Live Sensor Trends
              </h2>
            </div>
            <div className="w-full h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={analytics.recent_readings.map((r) => ({
                    ...r,
                    time: formatTime(r.time),
                  }))}
                >
                  <defs>
                    <linearGradient id="colorTempChart" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f97316" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorHumidityChart" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorBatteryChart" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#f0f0f0" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    stroke="#6b7280"
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "white",
                      border: "1px solid #e5e7eb",
                      borderRadius: "8px",
                      fontSize: "12px",
                      padding: "8px",
                    }}
                    labelStyle={{ fontWeight: "bold", color: "#374151" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="Battery"
                    stroke="#22c55e"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorBatteryChart)"
                    name="Battery"
                  />
                  <Area
                    type="monotone"
                    dataKey="Temperature"
                    stroke="#f97316"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorTempChart)"
                    name="Temperature"
                  />
                  <Area
                    type="monotone"
                    dataKey="Humidity"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorHumidityChart)"
                    name="Humidity"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-4 md:gap-6 justify-center mt-6">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                <span className="text-sm text-gray-700 font-medium">
                  Temperature
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                <span className="text-sm text-gray-700 font-medium">Humidity</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="text-sm text-gray-700 font-medium">Battery</span>
              </div>
            </div>
          </div>
        ) : loading ? (
          <div className="bg-white rounded-2xl p-6 shadow-sm">
            <div className="h-64 flex items-center justify-center">
              <p className="text-gray-400">Loading chart data...</p>
            </div>
          </div>
        ) : null}

        {/* Anomalies Table */}
        <div className="bg-white rounded-2xl p-5 md:p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-red-100 rounded-xl flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h2 className="text-xl md:text-2xl font-bold text-gray-900">
              Anomaly Detection
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Time
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Battery
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-gray-700 uppercase tracking-wider hidden sm:table-cell">
                    Humidity
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-gray-700 uppercase tracking-wider hidden md:table-cell">
                    Motion
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Temperature
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {loading ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-4 py-8 text-center text-gray-400"
                    >
                      Loading anomalies...
                    </td>
                  </tr>
                ) : anomalies.length > 0 ? (
                  anomalies.map((r, i) => (
                    <tr key={i} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-sm text-gray-800 whitespace-nowrap font-medium">
                        {formatTime(r.time)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {r.Battery?.toFixed(2) ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700 hidden sm:table-cell">
                        {r.Humidity?.toFixed(2) ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700 hidden md:table-cell">
                        {r.Motion?.toFixed(0) ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {r.Temperature?.toFixed(2) ?? "-"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <svg className="w-12 h-12 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-sm text-gray-600 font-medium">
                          No anomalies detected - System healthy!
                        </span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <footer className="text-center text-gray-500 text-xs py-4">
          <p>
            © {new Date().getFullYear()} Smart Home Analytics Dashboard
          </p>
          <p className="mt-1">
            Powered by Machine Learning & Real-time IoT
          </p>
        </footer>
      </div>
    </div>
  );
}

export default Dashboard;