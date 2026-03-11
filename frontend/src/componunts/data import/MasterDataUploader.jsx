import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../utils/Api"; 

const MasterDataUploader = () => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async (e) => {
    e.preventDefault(); 
    if (!file) return alert("Select a file first!");

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);
      
      // CHANGED: We hit a specific endpoint for direct master table ingestion
      const response = await api.post("/upload/master-direct", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      console.log("Upload Success:", response.data);

      // CHANGED: No need to wait for a task_id. 
      // We assume direct upload is immediate, so we go straight to the main Dashboard
      // to see the new data in the 'master_table'.
      navigate(`/dashboard/masterdata/dashboard`);

    } catch (error) {
      console.error("Master Upload Error:", error);
      alert("Upload failed. Check console for details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-white rounded-lg shadow-md border-t-4 border-indigo-600">
      <h2 className="text-xl font-bold mb-4 text-gray-900">Import to Master Table</h2>
      <p className="text-sm text-gray-500 mb-6">
        This will directly insert records into the <strong>master_table</strong>. 
        Ensure your CSV headers match the database schema.
      </p>
      
      <form onSubmit={handleUpload} className="flex flex-col gap-4">
        <div className="relative border-2 border-dashed border-gray-300 rounded-lg p-6 hover:bg-gray-50 transition text-center">
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div className="text-gray-500">
                {file ? (
                    <span className="font-semibold text-indigo-600">{file.name}</span>
                ) : (
                    <span>Click to browse or drag CSV here</span>
                )}
            </div>
        </div>
        
        <button
          type="submit"
          disabled={loading || !file}
          className={`py-3 px-4 rounded-lg font-bold text-white shadow-sm transition-all ${
            loading ? "bg-indigo-300 cursor-not-allowed" : "bg-indigo-600 hover:bg-indigo-700 hover:shadow-md"
          }`}
        >
          {loading ? "Importing Data..." : "Upload to Database"}
        </button>
      </form>
    </div>
  );
};

export default MasterDataUploader;