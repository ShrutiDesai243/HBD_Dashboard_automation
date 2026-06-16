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
const IconPlus = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
  </svg>
);
const IconChevronRight = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
);
const IconChevronDown = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
  </svg>
);
const IconEdit = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
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
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
  </svg>
);

/* ================================================================
   STAT CARD
   ================================================================ */
const StatCard = ({ label, value, color, icon }) => {
  const colorMap = {
    blue: "from-blue-500 to-blue-600",
    green: "from-green-500 to-green-600",
    red: "from-red-500 to-red-600",
    purple: "from-purple-500 to-purple-600",
  };
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-300 p-5 flex items-center gap-4">
      <div className={`bg-gradient-to-br ${colorMap[color] || colorMap.blue} p-3 rounded-lg text-white shrink-0`}>
        {icon || <IconFolder />}
      </div>
      <div>
        <Typography className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</Typography>
        <Typography variant="h4" className="text-gray-800 font-bold">{value}</Typography>
      </div>
    </div>
  );
};

/* ================================================================
   MODAL BACKDROP
   ================================================================ */
const Modal = ({ open, onClose, title, children }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <Typography variant="h5" className="text-gray-800 font-semibold">{title}</Typography>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 transition-colors">
            <IconX />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
};

/* ================================================================
   CONFIRM DIALOG
   ================================================================ */
const ConfirmDialog = ({ open, onClose, onConfirm, title, message, confirmLabel, confirmColor }) => (
  <Modal open={open} onClose={onClose} title={title || "Confirm"}>
    <Typography className="text-gray-600 mb-6">{message}</Typography>
    <div className="flex justify-end gap-3">
      <Button variant="outlined" color="gray" size="sm" onClick={onClose}>Cancel</Button>
      <Button color={confirmColor || "red"} size="sm" onClick={onConfirm}>{confirmLabel || "Confirm"}</Button>
    </div>
  </Modal>
);

/* ================================================================
   TREE NODE
   ================================================================ */
const TreeNode = ({ node, depth = 0, expanded, onToggle, onEdit, onDeactivate, onReactivate, searchTerm }) => {
  const isExpanded = expanded[node.id];
  const hasChildren = node.children && node.children.length > 0;
  const isActive = node.is_active !== false;

  const highlightMatch = (text) => {
    if (!searchTerm) return text;
    const idx = text.toLowerCase().indexOf(searchTerm.toLowerCase());
    if (idx === -1) return text;
    return (
      <>
        {text.slice(0, idx)}
        <span className="bg-yellow-200 rounded px-0.5">{text.slice(idx, idx + searchTerm.length)}</span>
        {text.slice(idx + searchTerm.length)}
      </>
    );
  };

  return (
    <div>
      <div
        className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg transition-all duration-200 hover:bg-blue-50/60 ${
          !isActive ? "opacity-60" : ""
        }`}
        style={{ paddingLeft: `${depth * 28 + 12}px` }}
      >
        {/* Expand/Collapse Toggle */}
        <button
          onClick={() => hasChildren && onToggle(node.id)}
          className={`p-0.5 rounded transition-transform duration-200 ${hasChildren ? "text-gray-500 hover:text-blue-600 cursor-pointer" : "text-transparent cursor-default"}`}
          style={{ transform: isExpanded ? "rotate(0deg)" : "rotate(0deg)" }}
        >
          {hasChildren ? (isExpanded ? <IconChevronDown /> : <IconChevronRight />) : <span className="w-4 h-4 inline-block" />}
        </button>

        {/* Folder Icon */}
        <span className={`shrink-0 ${isActive ? "text-blue-500" : "text-gray-400"}`}>
          <IconFolder />
        </span>

        {/* Name */}
        <Typography className={`text-sm font-medium flex-1 ${isActive ? "text-gray-800" : "text-gray-500 line-through"}`}>
          {highlightMatch(node.name)}
        </Typography>

        {/* Level Badge */}
        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-50 text-blue-700 border border-blue-200">
          L{node.level ?? depth + 1}
        </span>

        {/* Children Count */}
        {hasChildren && (
          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
            {node.children.length} children
          </span>
        )}

        {/* Status Badge */}
        <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
          isActive ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-600 border border-red-200"
        }`}>
          {isActive ? "Active" : "Inactive"}
        </span>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
          <button
            onClick={() => onEdit(node)}
            className="p-1.5 rounded-lg hover:bg-blue-100 text-blue-600 transition-colors"
            title="Edit"
          >
            <IconEdit />
          </button>
          {isActive ? (
            <button
              onClick={() => onDeactivate(node)}
              className="p-1.5 rounded-lg hover:bg-red-100 text-red-500 transition-colors"
              title="Deactivate"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            </button>
          ) : (
            <button
              onClick={() => onReactivate(node)}
              className="p-1.5 rounded-lg hover:bg-green-100 text-green-600 transition-colors"
              title="Reactivate"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Children */}
      {isExpanded && hasChildren && (
        <div className="transition-all duration-200">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              onEdit={onEdit}
              onDeactivate={onDeactivate}
              onReactivate={onReactivate}
              searchTerm={searchTerm}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/* ================================================================
   FLATTEN TREE HELPER
   ================================================================ */
const flattenTree = (nodes, result = []) => {
  for (const node of nodes) {
    result.push({ id: node.id, name: node.name, level: node.level });
    if (node.children && node.children.length > 0) {
      flattenTree(node.children, result);
    }
  }
  return result;
};

/* ================================================================
   MAIN COMPONENT
   ================================================================ */
const MasterCategoryManager = () => {
  const [treeData, setTreeData] = useState([]);
  const [flatData, setFlatData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [expanded, setExpanded] = useState({});

  // Stats
  const [stats, setStats] = useState({ total: 0, active: 0, inactive: 0, level1: 0 });

  // Add Modal
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addName, setAddName] = useState("");
  const [addParentId, setAddParentId] = useState("");
  const [addLoading, setAddLoading] = useState(false);

  // Edit Modal
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editNode, setEditNode] = useState(null);
  const [editName, setEditName] = useState("");
  const [editParentId, setEditParentId] = useState("");
  const [editLoading, setEditLoading] = useState(false);

  // Confirm Dialog
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [confirmNode, setConfirmNode] = useState(null);

  /* ---------- FETCH TREE ---------- */
  const fetchTree = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get("/master-categories/tree");
      const tree = response.data?.data || response.data || [];
      setTreeData(tree);
      setFlatData(flattenTree(tree));
      computeStats(tree);
    } catch (err) {
      console.error("Fetch Tree Error:", err);
      setError("Failed to fetch category tree.");
    } finally {
      setLoading(false);
    }
  }, []);

  /* ---------- SEARCH ---------- */
  const fetchSearch = useCallback(async (term) => {
    if (!term.trim()) {
      fetchTree();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.get("/master-categories/search", { params: { q: term } });
      const tree = response.data?.data || response.data || [];
      setTreeData(tree);
      // Auto-expand all when searching
      const allIds = {};
      const expandAll = (nodes) => {
        nodes.forEach((n) => {
          allIds[n.id] = true;
          if (n.children) expandAll(n.children);
        });
      };
      expandAll(tree);
      setExpanded(allIds);
    } catch (err) {
      console.error("Search Error:", err);
      setError("Search failed.");
    } finally {
      setLoading(false);
    }
  }, [fetchTree]);

  /* ---------- COMPUTE STATS ---------- */
  const computeStats = (tree) => {
    let total = 0, active = 0, inactive = 0, level1 = 0;
    const walk = (nodes, depth = 1) => {
      nodes.forEach((n) => {
        total++;
        if (n.is_active !== false) active++;
        else inactive++;
        if (depth === 1) level1++;
        if (n.children) walk(n.children, depth + 1);
      });
    };
    walk(tree);
    setStats({ total, active, inactive, level1 });
  };

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  /* ---------- SEARCH DEBOUNCE ---------- */
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchTerm) {
        fetchSearch(searchTerm);
      } else {
        fetchTree();
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [searchTerm, fetchSearch, fetchTree]);

  /* ---------- TOGGLE EXPAND ---------- */
  const handleToggle = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  /* ---------- EXPAND / COLLAPSE ALL ---------- */
  const expandAll = () => {
    const allIds = {};
    const walk = (nodes) => {
      nodes.forEach((n) => {
        allIds[n.id] = true;
        if (n.children) walk(n.children);
      });
    };
    walk(treeData);
    setExpanded(allIds);
  };

  const collapseAll = () => setExpanded({});

  /* ---------- ADD CATEGORY ---------- */
  const handleAdd = async () => {
    if (!addName.trim()) return;
    setAddLoading(true);
    try {
      const body = { name: addName.trim() };
      if (addParentId) body.parent_id = Number(addParentId);
      await api.post("/master-categories/", body);
      setAddModalOpen(false);
      setAddName("");
      setAddParentId("");
      fetchTree();
    } catch (err) {
      console.error("Add Error:", err);
      setError("Failed to add category.");
    } finally {
      setAddLoading(false);
    }
  };

  /* ---------- EDIT CATEGORY ---------- */
  const openEdit = (node) => {
    setEditNode(node);
    setEditName(node.name);
    setEditParentId(node.parent_id || "");
    setEditModalOpen(true);
  };

  const handleEdit = async () => {
    if (!editName.trim() || !editNode) return;
    setEditLoading(true);
    try {
      const body = { name: editName.trim() };
      if (editParentId) body.parent_id = Number(editParentId);
      await api.put(`/master-categories/${editNode.id}`, body);
      setEditModalOpen(false);
      setEditNode(null);
      fetchTree();
    } catch (err) {
      console.error("Edit Error:", err);
      setError("Failed to update category.");
    } finally {
      setEditLoading(false);
    }
  };

  /* ---------- DEACTIVATE / REACTIVATE ---------- */
  const openDeactivateConfirm = (node) => {
    setConfirmNode(node);
    setConfirmAction("deactivate");
    setConfirmOpen(true);
  };

  const openReactivateConfirm = (node) => {
    setConfirmNode(node);
    setConfirmAction("reactivate");
    setConfirmOpen(true);
  };

  const handleConfirmAction = async () => {
    if (!confirmNode) return;
    try {
      if (confirmAction === "deactivate") {
        await api.put(`/master-categories/${confirmNode.id}/deactivate`);
      } else {
        await api.put(`/master-categories/${confirmNode.id}/reactivate`);
      }
      setConfirmOpen(false);
      setConfirmNode(null);
      fetchTree();
    } catch (err) {
      console.error(`${confirmAction} Error:`, err);
      setError(`Failed to ${confirmAction} category.`);
      setConfirmOpen(false);
    }
  };

  /* ---------- PARENT OPTIONS ---------- */
  const parentOptions = useMemo(() => {
    return flatData.filter((n) => editNode ? n.id !== editNode.id : true);
  }, [flatData, editNode]);

  return (
    <div className="mt-8 px-4">
      {/* ========== STATS CARDS ========== */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Categories" value={stats.total} color="blue" icon={
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        } />
        <StatCard label="Active" value={stats.active} color="green" icon={
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        } />
        <StatCard label="Inactive" value={stats.inactive} color="red" icon={
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
          </svg>
        } />
        <StatCard label="Root Categories (L1)" value={stats.level1} color="purple" icon={
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
        } />
      </div>

      {/* ========== MAIN CARD ========== */}
      <Card className="border border-gray-200 shadow-sm rounded-xl bg-white">
        {/* ---------- HEADER ---------- */}
        <CardHeader
          floated={false}
          shadow={false}
          className="bg-gray-100 border-b border-gray-300 px-6 py-4 rounded-t-xl"
        >
          <div className="flex flex-col md:flex-row gap-4 md:items-center md:justify-between mb-4">
            <div>
              <Typography variant="h5" className="text-gray-800 font-semibold leading-tight">
                Master Category Manager
              </Typography>
              <Typography color="gray" className="mt-1 font-normal text-sm">
                Manage your category hierarchy — {stats.total} categories across {stats.level1} root nodes
              </Typography>
            </div>

            <div className="flex items-center gap-2">
              <Button
                onClick={expandAll}
                variant="outlined"
                color="gray"
                size="sm"
                className="whitespace-nowrap"
              >
                Expand All
              </Button>
              <Button
                onClick={collapseAll}
                variant="outlined"
                color="gray"
                size="sm"
                className="whitespace-nowrap"
              >
                Collapse All
              </Button>
              <Button
                onClick={() => { setAddName(""); setAddParentId(""); setAddModalOpen(true); }}
                color="blue"
                size="sm"
                className="flex items-center gap-1.5 whitespace-nowrap"
              >
                <IconPlus /> Add Category
              </Button>
            </div>
          </div>

          {/* ---------- SEARCH BAR ---------- */}
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
              <IconSearch />
            </span>
            <input
              type="text"
              placeholder="Search categories..."
              className="border border-gray-300 rounded-lg pl-10 pr-4 py-2.5 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <IconX />
              </button>
            )}
          </div>
        </CardHeader>

        {/* ---------- ERROR STATE ---------- */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm font-medium flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
              <IconX />
            </button>
          </div>
        )}

        {/* ---------- TREE BODY ---------- */}
        <CardBody className="px-4 pt-2 pb-4">
          {loading ? (
            <div className="flex flex-col justify-center py-20 items-center gap-3">
              <Spinner className="h-10 w-10 text-blue-500" />
              <Typography className="animate-pulse text-gray-600 font-medium">
                Loading Categories...
              </Typography>
            </div>
          ) : treeData.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <IconFolder />
              <Typography className="mt-3 text-gray-500 font-medium">No categories found</Typography>
              <Typography className="text-sm text-gray-400 mt-1">Create your first category to get started</Typography>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {treeData.map((node) => (
                <TreeNode
                  key={node.id}
                  node={node}
                  depth={0}
                  expanded={expanded}
                  onToggle={handleToggle}
                  onEdit={openEdit}
                  onDeactivate={openDeactivateConfirm}
                  onReactivate={openReactivateConfirm}
                  searchTerm={searchTerm}
                />
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {/* ========== ADD MODAL ========== */}
      <Modal open={addModalOpen} onClose={() => setAddModalOpen(false)} title="Add New Category">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Category Name</label>
            <input
              type="text"
              placeholder="Enter category name..."
              className="border border-gray-300 rounded-lg px-3 py-2.5 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Parent Category (optional)</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2.5 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white"
              value={addParentId}
              onChange={(e) => setAddParentId(e.target.value)}
            >
              <option value="">— Root (no parent) —</option>
              {flatData.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {"  ".repeat((cat.level || 1) - 1)}{"└ "}{cat.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outlined" color="gray" size="sm" onClick={() => setAddModalOpen(false)}>
              Cancel
            </Button>
            <Button color="blue" size="sm" onClick={handleAdd} disabled={addLoading || !addName.trim()}>
              {addLoading ? <Spinner className="h-4 w-4" /> : "Create Category"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ========== EDIT MODAL ========== */}
      <Modal open={editModalOpen} onClose={() => setEditModalOpen(false)} title="Edit Category">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Category Name</label>
            <input
              type="text"
              placeholder="Enter category name..."
              className="border border-gray-300 rounded-lg px-3 py-2.5 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Parent Category</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2.5 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white"
              value={editParentId}
              onChange={(e) => setEditParentId(e.target.value)}
            >
              <option value="">— Root (no parent) —</option>
              {parentOptions.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {"  ".repeat((cat.level || 1) - 1)}{"└ "}{cat.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outlined" color="gray" size="sm" onClick={() => setEditModalOpen(false)}>
              Cancel
            </Button>
            <Button color="blue" size="sm" onClick={handleEdit} disabled={editLoading || !editName.trim()}>
              {editLoading ? <Spinner className="h-4 w-4" /> : "Save Changes"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ========== CONFIRM DIALOG ========== */}
      <ConfirmDialog
        open={confirmOpen}
        onClose={() => { setConfirmOpen(false); setConfirmNode(null); }}
        onConfirm={handleConfirmAction}
        title={confirmAction === "deactivate" ? "Deactivate Category" : "Reactivate Category"}
        message={
          confirmAction === "deactivate"
            ? `Are you sure you want to deactivate "${confirmNode?.name}"? This will soft-delete the category and it can be reactivated later.`
            : `Are you sure you want to reactivate "${confirmNode?.name}"?`
        }
        confirmLabel={confirmAction === "deactivate" ? "Deactivate" : "Reactivate"}
        confirmColor={confirmAction === "deactivate" ? "red" : "green"}
      />
    </div>
  );
};

export default MasterCategoryManager;
