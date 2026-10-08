const API = "http://localhost:8001";

export async function upload(file) {
    const form = new FormData();
    form.append("file", file);

    const r = await fetch(`${API}/upload`, {
        method: "POST",
        body: form
    });

    return r.json();
}

export async function getSlice(session, z) {
    const r = await fetch(`${API}/slice/${session}/${z}`);
    const blob = await r.blob();
    return URL.createObjectURL(blob);
}

export async function getSliceRaw(session, z) {
    const r = await fetch(`${API}/slice-raw/${session}/${z}`);
    const blob = await r.blob();
    return URL.createObjectURL(blob);
}