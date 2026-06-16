import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Button,
  Spinner,
} from "@material-tailwind/react";
import React, { useState, useEffect, useCallback, useMemo } from "react";
import api from "../../utils/Api";

/* ================================================================
   ICONS (inline SVG helpers)
   ================================================================ */
const IconRefresh = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8H18" />
  </svg>
);
const IconCheck = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);
const IconLink = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
  </svg>
);
const IconBan = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
  </svg>
);
const IconSearch = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
);
const IconX = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);
const IconFolder = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
  </svg>
);
const IconChevronRight = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
);
const IconChevronDown = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
  </svg>
);
const IconPlus = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
  </svg>
);
const IconTrash = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);
const IconCog = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

/* ================================================================
   STAT CARD
   ================================================================ */
const StatCard = ({ platform, stats }) => {
  const { total = 0, mapped = 0, pending = 0, unmapped = 0 } = stats || {};
  const percentMapped = total > 0 ? Math.round((mapped / total) * 100) : 0;

  const getPlatformColors = (name) => {
    const maps = {
      bigbasket: { bg: "from-green-50 to-emerald-50/30", border: "border-green-100", text: "text-green-700", bar: "bg-green-500" },
      blinkit: { bg: "from-amber-50 to-yellow-50/30", border: "border-yellow-100", text: "text-yellow-800", bar: "bg-yellow-500" },
      zepto: { bg: "from-purple-50 to-indigo-50/30", border: "border-purple-100", text: "text-purple-700", bar: "bg-purple-500" },
      dmart: { bg: "from-blue-50 to-indigo-50/30", border: "border-blue-100", text: "text-blue-700", bar: "bg-blue-500" },
      indiamart: { bg: "from-cyan-50 to-teal-50/30", border: "border-teal-100", text: "text-teal-700", bar: "bg-teal-500" },
      amazon: { bg: "from-orange-50 to-yellow-50/30", border: "border-orange-100", text: "text-orange-800", bar: "bg-orange-500" },
      flipkart: { bg: "from-sky-50 to-blue-50/30", border: "border-sky-100", text: "text-sky-700", bar: "bg-sky-500" },
      jiomart: { bg: "from-orange-50 to-red-50/30", border: "border-orange-100", text: "text-orange-700", bar: "bg-orange-500" },
    };
    return maps[name.toLowerCase()] || { bg: "from-gray-50 to-gray-100", border: "border-gray-200", text: "text-gray-700", bar: "bg-blue-500" };
  };

  const colors = getPlatformColors(platform);

  return (
    <div className={`bg-white rounded-xl border ${colors.border} p-4 shadow-sm hover:shadow-md transition-all duration-300`}>
      <div className="flex justify-between items-center mb-3">
        <Typography variant="h6" className={`font-bold capitalize ${colors.text} truncate max-w-[60%]`} title={platform}>
          {platform}
        </Typography>
        <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full ${colors.bar} text-white shrink-0`}>
          {percentMapped}% Mapped
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-1.5 text-[11px] text-gray-500 mt-2">
        <div className="flex justify-between border-b border-gray-100 pb-0.5 pr-1">
          <span>Total:</span>
          <span className="font-bold text-gray-800">{total}</span>
        </div>
        <div className="flex justify-between border-b border-gray-100 pb-0.5 pl-1">
          <span>Mapped:</span>
          <span className="font-bold text-green-700">{mapped}</span>
        </div>
        <div className="flex justify-between pr-1">
          <span>Pend:</span>
          <span className="font-bold text-orange-700">{pending}</span>
        </div>
        <div className="flex justify-between pl-1">
          <span>Unmp:</span>
          <span className="font-bold text-red-600">{unmapped}</span>
        </div>
      </div>
      {/* Progress Bar */}
      <div className="w-full bg-gray-200/80 rounded-full h-1.5 mt-3.5 overflow-hidden">
        <div className={`h-full ${colors.bar} transition-all duration-500`} style={{ width: `${percentMapped}%` }} />
      </div>
    </div>
  );
};

/* ================================================================
   MODAL
   ================================================================ */
const Modal = ({ open, onClose, title, children }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-xl mx-4 max-h-[85vh] flex flex-col animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0">
          <Typography variant="h5" className="text-gray-800 font-semibold">{title}</Typography>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 transition-colors">
            <IconX />
          </button>
        </div>
        <div className="px-6 py-5 overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  );
};

/* ================================================================
   MAPPING TARGET SELECTOR TREE
   ================================================================ */
const SelectorTreeNode = ({ node, depth = 0, expanded, onToggle, onSelect, selectedId }) => {
  const isExpanded = expanded[node.id];
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = selectedId === node.id;

  return (
    <div>
      <div
        className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all duration-150 ${
          isSelected ? "bg-blue-50 text-blue-700 font-semibold" : "hover:bg-gray-50 text-gray-700"
        }`}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => onSelect(node)}
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (hasChildren) onToggle(node.id);
          }}
          className={`p-0.5 rounded hover:bg-gray-200 transition-colors ${
            hasChildren ? "text-gray-500" : "text-transparent cursor-default"
          }`}
        >
          {hasChildren ? (isExpanded ? <IconChevronDown /> : <IconChevronRight />) : <span className="w-3.5 h-3.5 inline-block" />}
        </button>

        <span className={`shrink-0 ${isSelected ? "text-blue-600" : "text-gray-400"}`}>
          <IconFolder />
        </span>

        <span className="text-sm flex-1 truncate">{node.name}</span>
        <span className="text-xs px-1.5 py-0.2 bg-gray-100 text-gray-500 rounded border border-gray-200/80">L{node.level}</span>
      </div>

      {isExpanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <SelectorTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              onSelect={onSelect}
              selectedId={selectedId}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/* ================================================================
   MAIN DASHBOARD COMPONENT
   ================================================================ */
const CategoryMappingDashboard = () => {
  // Navigation tabs: 'mappings' | 'platforms' | 'synonyms'
  const [activeTab, setActiveTab] = useState("mappings");

  // Mappings list state
  const [mappings, setMappings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [approvingAll, setApprovingAll] = useState(false);


  // Filters state
  const [platformFilter, setPlatformFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Dynamic platforms from database
  const [dbPlatforms, setDbPlatforms] = useState([]);
  const [dbPlatformsLoading, setDbPlatformsLoading] = useState(false);

  // Tree data for modal selector
  const [treeData, setTreeData] = useState([]);
  const [treeExpanded, setTreeExpanded] = useState({});
  const [treeLoading, setTreeLoading] = useState(false);

  // Mapping Modal state
  const [mappingModalOpen, setMappingModalOpen] = useState(false);
  const [activeMapping, setActiveMapping] = useState(null);
  const [selectedMasterNode, setSelectedMasterNode] = useState(null);
  const [modalSubmitLoading, setModalSubmitLoading] = useState(false);

  // Platforms Config Settings State
  const [newPlatformModalOpen, setNewPlatformModalOpen] = useState(false);
  const [newPlatformName, setNewPlatformName] = useState("");
  const [newPlatformQuery, setNewPlatformQuery] = useState("");
  const [editingPlatform, setEditingPlatform] = useState(null);
  const [platformSubmitLoading, setPlatformSubmitLoading] = useState(false);

  // Synonyms Settings State
  const [synonyms, setSynonyms] = useState([]);
  const [synonymsLoading, setSynonymsLoading] = useState(false);
  const [synonymSearch, setSynonymSearch] = useState("");
  const [synonymPage, setSynonymPage] = useState(1);
  const [synonymTotalPages, setSynonymTotalPages] = useState(1);
  const [newSynonymOpen, setNewSynonymOpen] = useState(false);
  const [synonymRaw, setSynonymRaw] = useState("");
  const [synonymCanonical, setSynonymCanonical] = useState("");
  const [synonymSubmitLoading, setSynonymSubmitLoading] = useState(false);

  // Default fallback platforms list if dynamic list is loading or empty
  const defaultPlatforms = ["BigBasket", "Blinkit", "Zepto", "DMart", "IndiaMart", "Amazon", "Flipkart", "JioMart"];

  const platformsList = useMemo(() => {
    if (dbPlatforms.length > 0) {
      return dbPlatforms.filter(p => p.is_active).map(p => p.platform_name);
    }
    return defaultPlatforms;
  }, [dbPlatforms]);

  /* ---------- FETCH DYNAMIC PLATFORMS ---------- */
  const fetchDbPlatforms = useCallback(async () => {
    setDbPlatformsLoading(true);
    try {
      const response = await api.get("/category-mapping/settings/platforms");
      setDbPlatforms(response.data?.data || []);
    } catch (err) {
      console.error("Fetch DB Platforms Error:", err);
    } finally {
      setDbPlatformsLoading(false);
    }
  }, []);

  /* ---------- FETCH MAPPINGS ---------- */
  const fetchMappings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        platform: platformFilter === "all" ? "" : platformFilter,
        status: statusFilter,
        search: searchTerm.trim(),
        page: page,
        limit: 15,
      };
      const response = await api.get("/category-mapping/", { params });
      setMappings(response.data?.data || []);
      setTotalPages(response.data?.total_pages || 1);
      setTotalCount(response.data?.total_count || 0);
    } catch (err) {
      console.error("Fetch Mappings Error:", err);
      setError("Failed to fetch mappings.");
    } finally {
      setLoading(false);
    }
  }, [platformFilter, statusFilter, searchTerm, page]);

  /* ---------- FETCH STATS ---------- */
  const fetchStats = useCallback(async () => {
    try {
      const response = await api.get("/category-mapping/stats");
      setStats(response.data?.data || []);
    } catch (err) {
      console.error("Fetch Stats Error:", err);
    }
  }, []);

  /* ---------- FETCH SYNONYMS ---------- */
  const fetchSynonyms = useCallback(async () => {
    setSynonymsLoading(true);
    try {
      const params = {
        search: synonymSearch.trim(),
        page: synonymPage,
        limit: 15,
      };
      const response = await api.get("/category-mapping/settings/synonyms", { params });
      setSynonyms(response.data?.data || []);
      setSynonymTotalPages(response.data?.total_pages || 1);
    } catch (err) {
      console.error("Fetch Synonyms Error:", err);
    } finally {
      setSynonymsLoading(false);
    }
  }, [synonymSearch, synonymPage]);

  /* ---------- FETCH MASTER TREE ---------- */
  const fetchMasterTree = async () => {
    setTreeLoading(true);
    try {
      const response = await api.get("/master-categories/tree");
      setTreeData(response.data?.data || []);
    } catch (err) {
      console.error("Fetch Master Tree Error:", err);
    } finally {
      setTreeLoading(false);
    }
  };

  useEffect(() => {
    fetchDbPlatforms();
    fetchStats();
  }, [fetchDbPlatforms, fetchStats]);

  useEffect(() => {
    if (activeTab === "mappings") {
      fetchMappings();
    } else if (activeTab === "synonyms") {
      fetchSynonyms();
    }
  }, [activeTab, fetchMappings, fetchSynonyms]);

  /* ---------- DEBOUNCE SEARCH ---------- */
  useEffect(() => {
    const timer = setTimeout(() => {
      if (activeTab === "mappings") {
        setPage(1);
        fetchMappings();
      }
    }, 450);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (activeTab === "synonyms") {
        setSynonymPage(1);
        fetchSynonyms();
      }
    }, 450);
    return () => clearTimeout(timer);
  }, [synonymSearch]);

  /* ---------- SYNC ALL ---------- */
  const handleSyncAll = async () => {
    setSyncing(true);
    setError(null);
    try {
      await api.post("/category-mapping/sync");
      fetchStats();
      if (activeTab === "mappings") fetchMappings();
    } catch (err) {
      console.error("Sync Error:", err);
      setError("Failed to sync categories.");
    } finally {
      setSyncing(false);
    }
  };

  /* ---------- APPROVE ALL AUTO-MAP ---------- */
  const handleApproveAll = async () => {
    setApprovingAll(true);
    setError(null);
    try {
      await api.post("/category-mapping/approve-all", {
        platform: platformFilter === "all" ? "" : platformFilter,
      });
      fetchStats();
      if (activeTab === "mappings") fetchMappings();
    } catch (err) {
      console.error("Approve All Error:", err);
      setError("Failed to approve all mappings.");
    } finally {
      setApprovingAll(false);
    }
  };


  /* ---------- APPROVE AUTO-MAP ---------- */
  const handleApprove = async (id) => {
    try {
      await api.put(`/category-mapping/${id}/approve`);
      setMappings((prev) =>
        prev.map((m) =>
          m.id === id
            ? { ...m, mapping_status: "MANUALLY_MAPPED", confidence_score: 1.0 }
            : m
        )
      );
      fetchStats();
    } catch (err) {
      console.error("Approve Error:", err);
      setError("Failed to approve mapping.");
    }
  };

  /* ---------- MARK AS UNMAPPED ---------- */
  const handleUnmap = async (id) => {
    try {
      await api.put(`/category-mapping/${id}/unmap`);
      setMappings((prev) =>
        prev.map((m) =>
          m.id === id
            ? {
                ...m,
                mapping_status: "UNMAPPED",
                master_category_id: null,
                master_category_name: null,
                master_category_path: null,
                confidence_score: 0.0,
              }
            : m
        )
      );
      fetchStats();
    } catch (err) {
      console.error("Unmap Error:", err);
      setError("Failed to unmap entry.");
    }
  };

  /* ---------- OPEN MAPPING MODAL ---------- */
  const openMappingModal = (mapping) => {
    setActiveMapping(mapping);
    setSelectedMasterNode(null);
    setMappingModalOpen(true);
    fetchMasterTree();
  };

  /* ---------- CONFIRM MANUAL MAPPING ---------- */
  const handleConfirmMapping = async () => {
    if (!activeMapping || !selectedMasterNode) return;
    setModalSubmitLoading(true);
    try {
      const response = await api.put(`/category-mapping/${activeMapping.id}/map`, {
        master_category_id: selectedMasterNode.id,
      });
      const updated = response.data?.data || response.data;
      setMappings((prev) =>
        prev.map((m) => (m.id === activeMapping.id ? updated : m))
      );
      setMappingModalOpen(false);
      setActiveMapping(null);
      setSelectedMasterNode(null);
      fetchStats();
    } catch (err) {
      console.error("Manual Map Error:", err);
      setError("Failed to map category.");
    } finally {
      setModalSubmitLoading(false);
    }
  };

  /* ---------- SAVE PLATFORM SETTINGS ---------- */
  const handleSavePlatform = async () => {
    if (!newPlatformName.trim() || !newPlatformQuery.trim()) return;
    setPlatformSubmitLoading(true);
    try {
      const body = {
        platform_name: newPlatformName.trim(),
        query_sql: newPlatformQuery.trim(),
      };
      if (editingPlatform) {
        await api.put(`/category-mapping/settings/platforms/${editingPlatform.id}`, body);
      } else {
        await api.post("/category-mapping/settings/platforms", body);
      }
      setNewPlatformModalOpen(false);
      setEditingPlatform(null);
      setNewPlatformName("");
      setNewPlatformQuery("");
      fetchDbPlatforms();
    } catch (err) {
      console.error("Save Platform Error:", err);
      setError("Failed to save platform configuration.");
    } finally {
      setPlatformSubmitLoading(false);
    }
  };

  const openEditPlatform = (platform) => {
    setEditingPlatform(platform);
    setNewPlatformName(platform.platform_name);
    setNewPlatformQuery(platform.query_sql);
    setNewPlatformModalOpen(true);
  };

  const handleTogglePlatformActive = async (platform) => {
    try {
      await api.put(`/category-mapping/settings/platforms/${platform.id}`, {
        is_active: !platform.is_active,
      });
      fetchDbPlatforms();
    } catch (err) {
      console.error("Toggle Platform Error:", err);
    }
  };

  /* ---------- SAVE SYNONYM ---------- */
  const handleSaveSynonym = async () => {
    if (!synonymRaw.trim() || !synonymCanonical.trim()) return;
    setSynonymSubmitLoading(true);
    try {
      await api.post("/category-mapping/settings/synonyms", {
        raw_value: synonymRaw.trim(),
        canonical_value: synonymCanonical.trim(),
      });
      setNewSynonymOpen(false);
      setSynonymRaw("");
      setSynonymCanonical("");
      fetchSynonyms();
    } catch (err) {
      console.error("Save Synonym Error:", err);
      setError(err.response?.data?.message || "Failed to add synonym mapping.");
    } finally {
      setSynonymSubmitLoading(false);
    }
  };

  const handleDeleteSynonym = async (id) => {
    try {
      await api.delete(`/category-mapping/settings/synonyms/${id}`);
      setSynonyms((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      console.error("Delete Synonym Error:", err);
    }
  };

  const toggleTreeExpand = (id) => {
    setTreeExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getStatusBadge = (status) => {
    const maps = {
      MANUALLY_MAPPED: "bg-green-50 text-green-700 border-green-200",
      AUTO_MAPPED: "bg-blue-50 text-blue-700 border-blue-200",
      PENDING: "bg-orange-50 text-orange-700 border-orange-200",
      UNMAPPED: "bg-red-50 text-red-700 border-red-200",
    };
    const labels = {
      MANUALLY_MAPPED: "Mapped (Manual)",
      AUTO_MAPPED: "Auto Mapped",
      PENDING: "Pending",
      UNMAPPED: "Unmapped",
    };
    return (
      <span className={`px-2 py-0.5 text-xs font-semibold rounded-full border ${maps[status] || "bg-gray-50 text-gray-600 border-gray-200"}`}>
        {labels[status] || status}
      </span>
    );
  };

  const getPlatformBadge = (platform) => {
    const maps = {
      bigbasket: "bg-green-100 text-green-800",
      blinkit: "bg-yellow-100 text-yellow-900",
      zepto: "bg-purple-100 text-purple-800",
      dmart: "bg-blue-100 text-blue-800",
      indiamart: "bg-teal-100 text-teal-800",
      amazon: "bg-orange-100 text-orange-800",
      flipkart: "bg-sky-100 text-sky-800",
      jiomart: "bg-orange-100 text-orange-800",
    };
    return (
      <span className={`px-2 py-0.5 text-xs font-medium rounded-md uppercase tracking-wide ${maps[platform.toLowerCase()] || "bg-gray-100 text-gray-800"}`}>
        {platform}
      </span>
    );
  };

  return (
    <div className="mt-8 px-4">
      {/* ========== TOP STATS ROW ========== */}
      {activeTab === "mappings" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
          {platformsList.map((p) => {
            const platformStats = stats.find((s) => s.platform_name.toLowerCase() === p.toLowerCase()) || {
              platform_name: p,
              total: 0,
              mapped: 0,
              pending: 0,
              unmapped: 0,
            };
            return <StatCard key={p} platform={p} stats={platformStats} />;
          })}
        </div>
      )}

      {/* ========== MAIN CARD ========== */}
      <Card className="border border-gray-200 shadow-sm rounded-xl bg-white overflow-hidden">
        {/* ---------- TAB BAR HEADER ---------- */}
        <CardHeader
          floated={false}
          shadow={false}
          className="bg-gray-100 border-b border-gray-300 px-6 pt-4 pb-0 rounded-t-xl"
        >
          <div className="flex flex-col md:flex-row gap-4 md:items-center md:justify-between mb-4">
            <div>
              <Typography variant="h5" className="text-gray-800 font-semibold leading-tight">
                Category Mapping Master
              </Typography>
              <Typography color="gray" className="mt-1 font-normal text-sm">
                Fully dynamic database-driven category auto-sync, matching, and settings management
              </Typography>
            </div>

            <div className="flex items-center gap-2">
              <Button
                onClick={handleApproveAll}
                disabled={approvingAll || syncing}
                color="green"
                size="sm"
                className="flex items-center gap-1.5 whitespace-nowrap"
              >
                {approvingAll ? <Spinner className="h-4 w-4" /> : <IconCheck />}
                Approve All Auto-Mapped
              </Button>
              <Button
                onClick={handleSyncAll}
                disabled={syncing || approvingAll}
                color="blue"
                size="sm"
                className="flex items-center gap-1.5 whitespace-nowrap"
              >
                {syncing ? <Spinner className="h-4 w-4" /> : <IconRefresh />}
                Sync New Categories
              </Button>
            </div>
          </div>

          {/* Nav Tabs */}
          <div className="flex gap-4 border-b border-gray-200 shrink-0">
            <button
              onClick={() => setActiveTab("mappings")}
              className={`pb-3 text-sm font-semibold transition-all border-b-2 ${
                activeTab === "mappings" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Category Mappings
            </button>
            <button
              onClick={() => setActiveTab("platforms")}
              className={`pb-3 text-sm font-semibold transition-all border-b-2 ${
                activeTab === "platforms" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Platform Configurations
            </button>
            <button
              onClick={() => setActiveTab("synonyms")}
              className={`pb-3 text-sm font-semibold transition-all border-b-2 ${
                activeTab === "synonyms" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Synonyms Manager
            </button>
          </div>
        </CardHeader>

        {/* ---------- ERROR ALERT ---------- */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm font-medium flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
              <IconX />
            </button>
          </div>
        )}

        {/* ---------- TAB 1: MAPPINGS VIEW ---------- */}
        {activeTab === "mappings" && (
          <>
            {/* Filters */}
            <div className="bg-gray-50 border-b border-gray-200 px-6 py-4 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                  <IconSearch />
                </span>
                <input
                  type="text"
                  placeholder="Search raw category strings..."
                  className="border border-gray-300 rounded-lg pl-10 pr-4 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm bg-white"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <select
                className="border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white text-sm"
                value={platformFilter}
                onChange={(e) => { setPlatformFilter(e.target.value); setPage(1); }}
              >
                <option value="all">All Platforms</option>
                {platformsList.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>

              <select
                className="border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white text-sm"
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              >
                <option value="">All Statuses</option>
                <option value="PENDING">Pending Review</option>
                <option value="AUTO_MAPPED">Auto Mapped</option>
                <option value="MANUALLY_MAPPED">Manually Mapped</option>
                <option value="UNMAPPED">Unmapped</option>
              </select>
            </div>

            <CardBody className="p-0 overflow-x-auto">
              {loading ? (
                <div className="flex flex-col justify-center py-20 items-center gap-3">
                  <Spinner className="h-10 w-10 text-blue-500" />
                  <Typography className="animate-pulse text-gray-600 font-medium">Fetching Mappings...</Typography>
                </div>
              ) : mappings.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                  <IconLink />
                  <Typography className="mt-3 text-gray-500 font-medium">No mappings found</Typography>
                </div>
              ) : (
                <table className="w-full min-w-max table-auto text-left border-collapse">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 text-xs font-bold uppercase tracking-wider text-gray-500">
                      <th className="px-6 py-3.5">Platform</th>
                      <th className="px-6 py-3.5">Raw Category String</th>
                      <th className="px-6 py-3.5">Raw Subcategory</th>
                      <th className="px-6 py-3.5">Mapped Master Category</th>
                      <th className="px-6 py-3.5">Status</th>
                      <th className="px-6 py-3.5 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-sm text-gray-700 bg-white">
                    {mappings.map((m) => (
                      <tr key={m.id} className="hover:bg-gray-50/75 transition-colors">
                        <td className="px-6 py-4">{getPlatformBadge(m.platform_name)}</td>
                        <td className="px-6 py-4 font-medium text-gray-800">{m.platform_category_raw}</td>
                        <td className="px-6 py-4 text-gray-500">{m.platform_subcategory_raw || <span className="text-gray-300 italic">—</span>}</td>
                        <td className="px-6 py-4 max-w-xs truncate">
                          {m.master_category_name ? (
                            <div>
                              <span className="font-semibold text-gray-800">{m.master_category_name}</span>
                              <span className="block text-xs text-gray-400 font-normal truncate" title={m.master_category_path}>{m.master_category_path}</span>
                            </div>
                          ) : (
                            <span className="text-red-500 italic text-xs font-semibold">Not Mapped</span>
                          )}
                        </td>
                        <td className="px-6 py-4">{getStatusBadge(m.mapping_status)}</td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-center gap-2">
                            <Button size="sm" variant="outlined" color="blue" className="py-1.5 px-3 flex items-center gap-1 text-xs" onClick={() => openMappingModal(m)}>
                              <IconLink /> {m.master_category_id ? "Remap" : "Map"}
                            </Button>
                            {m.mapping_status === "AUTO_MAPPED" && (
                              <Button size="sm" color="green" className="py-1.5 px-3 flex items-center gap-1 text-xs" onClick={() => handleApprove(m.id)}>
                                <IconCheck /> Approve
                              </Button>
                            )}
                            {m.mapping_status !== "UNMAPPED" && (
                              <Button size="sm" variant="text" color="red" className="py-1.5 px-2.5 flex items-center gap-1 text-xs" onClick={() => handleUnmap(m.id)}>
                                <IconBan /> Unmap
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardBody>

            {!loading && totalCount > 0 && (
              <div className="flex items-center justify-between border-t border-gray-200 px-6 py-4 bg-gray-50 shrink-0">
                <Typography variant="small" color="gray" className="font-normal text-xs">
                  Showing page <span className="font-bold text-gray-800">{page}</span> of <span className="font-bold text-gray-800">{totalPages}</span> ({totalCount} items)
                </Typography>
                <div className="flex gap-2">
                  <Button variant="outlined" color="gray" size="sm" disabled={page === 1} onClick={() => setPage((prev) => Math.max(prev - 1, 1))}>Previous</Button>
                  <Button variant="outlined" color="gray" size="sm" disabled={page === totalPages} onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}>Next</Button>
                </div>
              </div>
            )}
          </>
        )}

        {/* ---------- TAB 2: PLATFORMS SETTINGS VIEW ---------- */}
        {activeTab === "platforms" && (
          <CardBody className="px-6 py-5">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Typography variant="h6" className="text-gray-800 font-bold">Scraper Database Bypasses</Typography>
                <Typography className="text-xs text-gray-500">Add, configure, or toggle which tables are scanned for category discovery.</Typography>
              </div>
              <Button
                color="blue"
                size="sm"
                className="flex items-center gap-1.5 text-xs font-bold"
                onClick={() => { setEditingPlatform(null); setNewPlatformName(""); setNewPlatformQuery(""); setNewPlatformModalOpen(true); }}
              >
                <IconPlus /> Add Platform Config
              </Button>
            </div>

            {dbPlatformsLoading ? (
              <div className="flex justify-center py-12"><Spinner className="h-8 w-8 text-blue-500" /></div>
            ) : dbPlatforms.length === 0 ? (
              <div className="text-center py-10 text-gray-400">No platforms configured. Click add.</div>
            ) : (
              <div className="overflow-x-auto border border-gray-200 rounded-lg">
                <table className="w-full text-left table-auto border-collapse text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 text-xs font-bold uppercase tracking-wider text-gray-500">
                      <th className="px-5 py-3">Platform Name</th>
                      <th className="px-5 py-3">SQL Category Search Query</th>
                      <th className="px-5 py-3 text-center">Status</th>
                      <th className="px-5 py-3 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {dbPlatforms.map((p) => (
                      <tr key={p.id} className="hover:bg-gray-50/50">
                        <td className="px-5 py-4 font-bold text-gray-800">{p.platform_name}</td>
                        <td className="px-5 py-4 font-mono text-xs max-w-md truncate text-gray-600" title={p.query_sql}>{p.query_sql}</td>
                        <td className="px-5 py-4 text-center">
                          <button
                            onClick={() => handleTogglePlatformActive(p)}
                            className={`px-3 py-1 text-xs font-bold rounded-full border transition-all ${
                              p.is_active ? "bg-green-50 text-green-700 border-green-200" : "bg-red-50 text-red-600 border-red-200"
                            }`}
                          >
                            {p.is_active ? "Active" : "Inactive"}
                          </button>
                        </td>
                        <td className="px-5 py-4 text-center">
                          <Button size="sm" variant="outlined" color="blue" className="px-3 py-1.5 text-xs font-bold" onClick={() => openEditPlatform(p)}>
                            Edit Query
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        )}

        {/* ---------- TAB 3: SYNONYMS MANAGER VIEW ---------- */}
        {activeTab === "synonyms" && (
          <>
            <div className="bg-gray-50 border-b border-gray-200 px-6 py-4 flex flex-col md:flex-row gap-4 items-center justify-between">
              <div className="relative w-full md:max-w-md">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                  <IconSearch />
                </span>
                <input
                  type="text"
                  placeholder="Search synonym rules..."
                  className="border border-gray-300 rounded-lg pl-10 pr-4 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm bg-white"
                  value={synonymSearch}
                  onChange={(e) => setSynonymSearch(e.target.value)}
                />
              </div>

              <Button
                color="blue"
                size="sm"
                className="flex items-center gap-1.5 text-xs font-bold shrink-0"
                onClick={() => { setSynonymRaw(""); setSynonymCanonical(""); setNewSynonymOpen(true); }}
              >
                <IconPlus /> Add Synonym Mapping
              </Button>
            </div>

            <CardBody className="p-0 overflow-x-auto">
              {synonymsLoading ? (
                <div className="flex justify-center py-20"><Spinner className="h-10 w-10 text-blue-500" /></div>
              ) : synonyms.length === 0 ? (
                <div className="text-center py-20 text-gray-400">No synonym mappings found.</div>
              ) : (
                <table className="w-full table-auto text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 text-xs font-bold uppercase tracking-wider text-gray-500">
                      <th className="px-6 py-3.5">Scraped Raw Category Value (Normalized)</th>
                      <th className="px-6 py-3.5">Canonical Target Category Name</th>
                      <th className="px-6 py-3.5 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white text-gray-700">
                    {synonyms.map((s) => (
                      <tr key={s.id} className="hover:bg-gray-50/50">
                        <td className="px-6 py-4 font-mono text-xs font-semibold text-gray-600">{s.raw_value}</td>
                        <td className="px-6 py-4 font-bold text-gray-800">{s.canonical_value}</td>
                        <td className="px-6 py-4 text-center">
                          <button
                            onClick={() => handleDeleteSynonym(s.id)}
                            className="p-2 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                            title="Delete Synonym"
                          >
                            <IconTrash />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardBody>

            {!synonymsLoading && synonyms.length > 0 && (
              <div className="flex items-center justify-between border-t border-gray-200 px-6 py-4 bg-gray-50 shrink-0">
                <Typography variant="small" color="gray" className="font-normal text-xs">
                  Showing page <span className="font-bold text-gray-800">{synonymPage}</span> of <span className="font-bold text-gray-800">{synonymTotalPages}</span>
                </Typography>
                <div className="flex gap-2">
                  <Button variant="outlined" color="gray" size="sm" disabled={synonymPage === 1} onClick={() => setSynonymPage((prev) => Math.max(prev - 1, 1))}>Previous</Button>
                  <Button variant="outlined" color="gray" size="sm" disabled={synonymPage === synonymTotalPages} onClick={() => setSynonymPage((prev) => Math.min(prev + 1, synonymTotalPages))}>Next</Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      {/* ========== MAPPING Tree Modal ========== */}
      <Modal
        open={mappingModalOpen}
        onClose={() => setMappingModalOpen(false)}
        title={activeMapping ? `Map Category: ${activeMapping.platform_category_raw}` : "Select Master Category"}
      >
        <div className="flex flex-col h-[55vh]">
          <div className="bg-blue-50/50 border border-blue-100 rounded-lg p-3 mb-4 shrink-0 text-xs">
            <Typography className="text-xs text-blue-800 font-semibold uppercase tracking-wider mb-1">Source Item Details</Typography>
            <div>Platform: <span className="font-bold uppercase text-blue-900">{activeMapping?.platform_name}</span></div>
            <div className="mt-1">Raw Subcategory: <span className="font-bold text-blue-900">{activeMapping?.platform_subcategory_raw || "—"}</span></div>
          </div>

          <Typography className="text-sm font-medium text-gray-700 mb-2 shrink-0">Select Target Master Category:</Typography>

          <div className="flex-1 overflow-y-auto border border-gray-200 rounded-lg p-2 bg-white">
            {treeLoading ? (
              <div className="flex flex-col justify-center h-full items-center"><Spinner className="h-8 w-8 text-blue-500" /></div>
            ) : (
              <div className="space-y-0.5">
                {treeData.map((node) => (
                  <SelectorTreeNode
                    key={node.id}
                    node={node}
                    depth={0}
                    expanded={treeExpanded}
                    onToggle={toggleTreeExpand}
                    onSelect={setSelectedMasterNode}
                    selectedId={selectedMasterNode?.id}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between shrink-0">
            <div className="text-xs">
              {selectedMasterNode ? (
                <div>
                  <span className="text-gray-500">Selected:</span>
                  <span className="block font-bold text-blue-600 truncate max-w-xs">{selectedMasterNode.name}</span>
                </div>
              ) : (
                <span className="text-red-500 italic">No category selected</span>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outlined" color="gray" size="sm" onClick={() => setMappingModalOpen(false)}>Cancel</Button>
              <Button color="blue" size="sm" onClick={handleConfirmMapping} disabled={modalSubmitLoading || !selectedMasterNode}>
                {modalSubmitLoading ? <Spinner className="h-4 w-4" /> : "Confirm Mapping"}
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* ========== PLATFORM SETTINGS MODAL ========== */}
      <Modal open={newPlatformModalOpen} onClose={() => setNewPlatformModalOpen(false)} title={editingPlatform ? "Edit Platform Query" : "Add Platform Config"}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Platform Name</label>
            <input
              type="text"
              placeholder="e.g. Flipkart"
              disabled={editingPlatform !== null}
              className="border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm bg-white disabled:bg-gray-100 disabled:text-gray-500"
              value={newPlatformName}
              onChange={(e) => setNewPlatformName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">SQL Category Retrieval Query</label>
            <textarea
              placeholder="SELECT DISTINCT main_category AS category, subcategory AS subcategory FROM ..."
              rows={5}
              className="border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm font-mono"
              value={newPlatformQuery}
              onChange={(e) => setNewPlatformQuery(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outlined" color="gray" size="sm" onClick={() => setNewPlatformModalOpen(false)}>Cancel</Button>
            <Button color="blue" size="sm" onClick={handleSavePlatform} disabled={platformSubmitLoading || !newPlatformName.trim() || !newPlatformQuery.trim()}>
              {platformSubmitLoading ? <Spinner className="h-4 w-4" /> : "Save Configuration"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ========== ADD SYNONYM MODAL ========== */}
      <Modal open={newSynonymOpen} onClose={() => setNewSynonymOpen(false)} title="Add Synonym Mapping Rule">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Scraped Raw Category Value</label>
            <input
              type="text"
              placeholder="e.g. fruits and veg"
              className="border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
              value={synonymRaw}
              onChange={(e) => setSynonymRaw(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Canonical Master Target Category</label>
            <input
              type="text"
              placeholder="e.g. Fruits & Vegetables"
              className="border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
              value={synonymCanonical}
              onChange={(e) => setSynonymCanonical(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outlined" color="gray" size="sm" onClick={() => setNewSynonymOpen(false)}>Cancel</Button>
            <Button color="blue" size="sm" onClick={handleSaveSynonym} disabled={synonymSubmitLoading || !synonymRaw.trim() || !synonymCanonical.trim()}>
              {synonymSubmitLoading ? <Spinner className="h-4 w-4" /> : "Add Rule"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default CategoryMappingDashboard;
