// src/App.jsx
// Simple client-side router — no react-router needed.
// /          → Home (main segmentation page)
// /beta-3d   → Beta3D (experimental 3D mesh viewer)
// /demo      → Demo mode

import "./App.css";
import Home from "./pages/Home";
import Beta3D from "./pages/Beta3D";
import Demo from "./pages/Demo";
import DemoResult from "./pages/DemoResult";

export default function App() {
    const path = window.location.pathname;

    if (path === "/beta-3d" || path === "/beta-3d/") {
        return <Beta3D />;
    }

    if (path === "/demo" || path === "/demo/") {
        return <Demo />;
    }

    if (path === "/demo-result" || path.startsWith("/demo-result")) {
    return <DemoResult />;
}

    return <Home />;
}