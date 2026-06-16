import axios from "axios";

const api = axios.create({
  // Direct connection to Flask backend on port 8001
  baseURL: `${import.meta.env.VITE_API_URL || "http://localhost:8001"}/api`, 
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;