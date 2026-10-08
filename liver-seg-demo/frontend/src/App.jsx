import "./styles/App.css";
import Home from "./pages/Home";
import Demo from "./pages/Demo";

export default function App() {
    const path = window.location.pathname;

    if (path === "/demo" || path === "/demo/")
        return <Demo />;

    return <Home />;
}