import axios from "axios";

const api = axios.create({
  // By using "/api", Nginx will know to forward this request to your Python backend
  baseURL: "/api", 
  headers: {
    "Content-Type": "application/json",
  },
});

export default api;