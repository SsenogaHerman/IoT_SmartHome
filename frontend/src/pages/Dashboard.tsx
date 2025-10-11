import { useEffect, useState } from "react";
import axios from "axios";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// --------------------
// ✅ Type Definitions
// --------------------
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
  predicted_next_temperature: number;
}

interface Anomaly {
  time: string;
  Battery: number;
  Humidity: number;
  Motion: number;
  Temperature: number;
}

// --------------------
// ✅ Dashboard Component
// --------------------
function Dashboard() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [prediction, setPrediction] = useState<Prediction | null>(null);

  // Flask API base URL — change this if deployed
  const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:5000";

  useEffect(() => {
    fetchAll();
  }, []);

  async function fetchAll() {
    try {
      // Fetch analytics summary
      const a = await axios.get<Analytics>(`${API_BASE}/analytics`);
      setAnalytics(a.data);

      // Fetch anomaly list
      const an = await axios.get<Anomaly[]>(`${API_BASE}/anomalies`);
      setAnomalies(Array.isArray(an.data) ? an.data : []);

      // Fetch temperature prediction
      const p = await axios.get<Prediction>(`${API_BASE}/predict`);
      setPrediction(p.data);
    } catch (e) {
      console.error("Fetch error:", e);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800 p-6">
      <header className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-indigo-600">
          Smart Home Sensor Dashboard
        </h1>
        <button
          onClick={fetchAll}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg transition-all shadow-md"
        >
          Refresh Data
        </button>
      </header>

      {/* Summary Cards */}
      <div className="grid md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-2xl shadow p-5 border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Avg Temperature
          </h2>
          <p className="text-3xl font-bold text-indigo-600">
            {analytics
              ? `${analytics.avg_temperature.toFixed(2)} °C`
              : "Loading..."}
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow p-5 border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Avg Humidity
          </h2>
          <p className="text-3xl font-bold text-blue-600">
            {analytics
              ? `${analytics.avg_humidity.toFixed(2)} %`
              : "Loading..."}
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow p-5 border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Avg Battery
          </h2>
          <p className="text-3xl font-bold text-green-600">
            {analytics
              ? `${analytics.avg_battery.toFixed(2)} %`
              : "Loading..."}
          </p>
        </div>
      </div>

      {/* Prediction Section */}
      <div className="bg-white rounded-2xl shadow p-6 mb-8 border border-gray-100">
        <h2 className="text-xl font-semibold text-gray-700 mb-4">
          Next Temperature Prediction
        </h2>
        {prediction?.predicted_next_temperature ? (
          <p className="text-2xl font-bold text-indigo-600">
            {prediction.predicted_next_temperature.toFixed(2)} °C
          </p>
        ) : (
          <p className="text-gray-500">Prediction not ready</p>
        )}
      </div>

      {/* Chart Section */}
      {analytics?.recent_readings ? (
        <div className="bg-white rounded-2xl shadow p-6 mb-8 border border-gray-100">
          <h2 className="text-xl font-semibold text-gray-700 mb-4">
            Recent Sensor Trends
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={analytics.recent_readings}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="Temperature"
                stroke="#6366f1"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="Humidity"
                stroke="#0ea5e9"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="Battery"
                stroke="#22c55e"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      {/* Anomalies Table */}
      <div className="bg-white rounded-2xl shadow p-6 border border-gray-100">
        <h2 className="text-xl font-semibold text-gray-700 mb-4">
          Recent Anomalies
        </h2>
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse border border-gray-200">
            <thead className="bg-indigo-600 text-white">
              <tr>
                <th className="px-4 py-2 border border-gray-200 text-left">Time</th>
                <th className="px-4 py-2 border border-gray-200 text-left">Battery</th>
                <th className="px-4 py-2 border border-gray-200 text-left">Humidity</th>
                <th className="px-4 py-2 border border-gray-200 text-left">Motion</th>
                <th className="px-4 py-2 border border-gray-200 text-left">Temperature</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.length > 0 ? (
                anomalies.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-2 border border-gray-200">{r.time}</td>
                    <td className="px-4 py-2 border border-gray-200">{r.Battery}</td>
                    <td className="px-4 py-2 border border-gray-200">{r.Humidity}</td>
                    <td className="px-4 py-2 border border-gray-200">{r.Motion}</td>
                    <td className="px-4 py-2 border border-gray-200">{r.Temperature}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={5}
                    className="text-center text-gray-500 py-4 border border-gray-200"
                  >
                    No anomalies detected
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <footer className="text-center text-gray-500 text-sm mt-8">
        © {new Date().getFullYear()} Smart Home Analytics Dashboard
      </footer>
    </div>
  );
}

export default Dashboard;
