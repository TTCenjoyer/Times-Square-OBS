import cv2, numpy as np, json
from numba import njit

W, H = 1080, 1920


def intersection(a, b, c, d):
    a, b, c, d = map(lambda v: np.asarray(v, np.float64), (a, b, c, d))
    M = np.column_stack((b - a, c - d))
    if abs(np.linalg.det(M)) < 1e-7:
        return b
    return a + np.linalg.solve(M, c - a)[0] * (b - a)


def corrected_screens(fr):
    screens = json.loads(json.dumps(fr["screens"]))
    wide = next((s for s in screens if s["id"] == "N11_WIDE"), None)
    if wide:
        p0, p1 = np.array(wide["corners"][:2], float)

        def atline(x):
            return [
                float(x),
                float(p0[1] + (x - p0[0]) * (p1[1] - p0[1]) / (p1[0] - p0[0])),
            ]

        p = np.array(wide["mask"], float)
        # Replace the stepped top boundary by the continuous shared row boundary.
        wide["mask"] = [
            atline(p[0, 0]),
            atline(p[-3, 0]),
            p[-2].tolist(),
            p[-1].tolist(),
        ]
        for s in screens:
            if s["id"] not in ["N07_TOP", "N08_TOP", "N09_ROUND", "N10_REAR"]:
                continue
            p = np.array(s["mask"], float)
            if len(p) == 4:
                p[2] = intersection(p[1], p[2], p0, p1)
                p[3] = intersection(p[0], p[3], p0, p1)
            else:
                p[-2] = intersection(p[-3], p[-2], p0, p1)
                p[-1] = intersection(p[0], p[-1], p0, p1)
            s["mask"] = p.tolist()
    return [s for s in screens if s["id"] not in ["N21_STAGE_FRONT", "N22_STAGE_SIDE"]]


def mesh(s):
    import triangle
    from scipy.sparse import coo_matrix, eye
    from scipy.sparse.linalg import spsolve

    pts = np.asarray(s["mask"], np.float64)
    corners = np.asarray(s["corners"], np.float32)
    hom = cv2.getPerspectiveTransform(
        corners, np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    )
    q = cv2.perspectiveTransform(pts[None, :, :].astype(np.float32), hom)[0].astype(
        float
    )
    # Remove adjacent duplicate boundary vertices.
    keep = np.r_[True, np.linalg.norm(np.diff(q, axis=0), axis=1) > 1e-7]
    q = q[keep]
    first = np.argmin(np.sum(q * q, axis=1))
    q = np.roll(q, -first, axis=0)
    if cv2.contourArea(q.astype(np.float32), oriented=True) < 0:
        q = np.concatenate((q[:1], q[:0:-1]))
    n = len(q)
    i1 = 1 + np.argmin(np.sum((q[1 : n - 2] - [1, 0]) ** 2, axis=1))
    i2 = i1 + 1 + np.argmin(np.sum((q[i1 + 1 : n - 1] - [1, 1]) ** 2, axis=1))
    i3 = i2 + 1 + np.argmin(np.sum((q[i2 + 1 :] - [0, 1]) ** 2, axis=1))
    anchors = [0, i1, i2, i3, n]
    target = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], float)
    attr = np.zeros((n, 2))
    closed = np.vstack((q, q[:1]))
    for j in range(4):
        a, b = anchors[j : j + 2]
        path = closed[a : b + 1]
        length = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
        length /= max(length[-1], 1e-10)
        attr[a:b] = target[j] + length[:-1, None] * (target[j + 1] - target[j])
    segments = np.column_stack((np.arange(n), np.roll(np.arange(n), -1)))
    spec = {
        "vertices": q,
        "segments": segments,
        "vertex_attributes": attr,
        "vertex_markers": np.ones((n, 1), np.int32),
    }
    result = triangle.triangulate(spec, "pq18a0.002Q")
    # Split interior chords whose two endpoints lie on one rectangle edge.
    # This keeps curved boundary ears connected to the interior of the map.
    for repeat in range(3):
        vertices = result["vertices"]
        boundary = result["vertex_markers"].ravel() != 0
        tris = result["triangles"]
        segset = {tuple(sorted(e)) for e in result["segments"]}
        edges = np.unique(
            np.sort(
                np.vstack((tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]])), axis=1
            ),
            axis=0,
        )
        chords = [
            e
            for e in edges
            if boundary[e[0]] and boundary[e[1]] and tuple(e) not in segset
        ]
        if not chords:
            break
        chords = np.array(chords)
        spec = {
            "vertices": np.vstack((vertices, vertices[chords].mean(axis=1))),
            "segments": result["segments"],
            "vertex_attributes": np.vstack(
                (result["vertex_attributes"], np.zeros((len(chords), 2)))
            ),
            "vertex_markers": np.r_[
                result["vertex_markers"].ravel(), np.zeros(len(chords), int)
            ][:, None],
        }
        result = triangle.triangulate(spec, "pq18a0.002Q")
    vertices = result["vertices"]
    tris = result["triangles"]
    boundary = result["vertex_markers"].ravel() != 0
    attr = result["vertex_attributes"]
    nv = len(vertices)
    rows = []
    cols = []
    values = []
    for k in range(3):
        ii = tris[:, k]
        jj = tris[:, (k + 1) % 3]
        kk = tris[:, (k + 2) % 3]
        va = vertices[jj] - vertices[ii]
        vb = vertices[kk] - vertices[ii]
        la = np.linalg.norm(va, axis=1)
        lb = np.linalg.norm(vb, axis=1)
        cross = np.abs(va[:, 0] * vb[:, 1] - va[:, 1] * vb[:, 0])
        half = cross / np.maximum(la * lb + (va * vb).sum(axis=1), 1e-14)
        rows.extend([ii, ii])
        cols.extend([jj, kk])
        values.extend([half / np.maximum(la, 1e-12), half / np.maximum(lb, 1e-12)])
    weight = coo_matrix(
        (np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))),
        shape=(nv, nv),
    ).tocsr()
    interior = np.flatnonzero(~boundary)
    bd = np.flatnonzero(boundary)
    weightsum = np.asarray(weight.sum(axis=1)).ravel()
    weight = weight.multiply(1 / np.maximum(weightsum, 1e-15)[:, None]).tocsr()
    if len(interior):
        attr[interior] = spsolve(
            eye(len(interior), format="csr") - weight[interior][:, interior],
            weight[interior][:, bd] @ attr[bd],
        )
    # Positive UV triangle areas prove the mesh has no flipped pieces.
    uvtri = attr[tris]
    uv_area = (uvtri[:, 1, 0] - uvtri[:, 0, 0]) * (uvtri[:, 2, 1] - uvtri[:, 0, 1]) - (
        uvtri[:, 1, 1] - uvtri[:, 0, 1]
    ) * (uvtri[:, 2, 0] - uvtri[:, 0, 0])
    bad = int(np.count_nonzero(uv_area < -1e-10))
    if bad:
        raise RuntimeError(f'Folded harmonic mapping: {s["id"]} ({bad})')
    inv = np.linalg.inv(hom)
    ph = np.column_stack((vertices, np.ones(nv))) @ inv.T
    xyz = ph[:, :2] / ph[:, 2:3]
    depth = 1 / ph[:, 2]
    return (
        np.ascontiguousarray(xyz),
        np.ascontiguousarray(np.column_stack((attr, depth))),
        np.ascontiguousarray(tris),
    )


@njit(cache=True)
def raster(xyz, uvz, tris, x0, y0, width, height):
    out = np.full((height, width, 2), -1, np.float32)
    folds = 0
    for tri in tris:
        a = xyz[tri[0]]
        b = xyz[tri[1]]
        c = xyz[tri[2]]
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-8:
            continue
        l = max(0, int(np.floor(min(a[0], b[0], c[0]))) - x0)
        r = min(width - 1, int(np.ceil(max(a[0], b[0], c[0]))) - x0)
        t = max(0, int(np.floor(min(a[1], b[1], c[1]))) - y0)
        bot = min(height - 1, int(np.ceil(max(a[1], b[1], c[1]))) - y0)
        if l > r or t > bot:
            continue
        if den < 0:
            folds += 1
        ua = uvz[tri[0]]
        ub = uvz[tri[1]]
        uc = uvz[tri[2]]
        for py in range(t, bot + 1):
            for px in range(l, r + 1):
                sx = px + x0
                sy = py + y0
                wa = ((b[1] - c[1]) * (sx - c[0]) + (c[0] - b[0]) * (sy - c[1])) / den
                wb = ((c[1] - a[1]) * (sx - c[0]) + (a[0] - c[0]) * (sy - c[1])) / den
                wc = 1 - wa - wb
                if wa >= -1e-5 and wb >= -1e-5 and wc >= -1e-5:
                    z = wa * ua[2] + wb * ub[2] + wc * uc[2]
                    if abs(z) > 1e-15:
                        out[py, px, 0] = (
                            wa * ua[0] * ua[2] + wb * ub[0] * ub[2] + wc * uc[0] * uc[2]
                        ) / z
                        out[py, px, 1] = (
                            wa * ua[1] * ua[2] + wb * ub[1] * ub[2] + wc * uc[1] * uc[2]
                        ) / z
    return out, folds


def fill_uv(fr, matte):
    ids = np.zeros((H, W), np.uint8)
    uv = np.zeros((H, W, 2), np.float32)
    folds = 0
    edge_filled = 0
    screens = corrected_screens(fr)
    for slot, s in enumerate(screens, 1):
        p = np.asarray(s["mask"], float)
        radius = int(np.ceil(s.get("overscan_pixels", 0)))
        x0 = max(0, int(np.floor(p[:, 0].min())) - radius - 2)
        x1 = min(W, int(np.ceil(p[:, 0].max())) + radius + 3)
        y0 = max(0, int(np.floor(p[:, 1].min())) - radius - 2)
        y1 = min(H, int(np.ceil(p[:, 1].max())) + radius + 3)
        if x1 <= x0 or y1 <= y0:
            continue
        wh, hh = x1 - x0, y1 - y0
        support = np.zeros((hh, wh), np.uint8)
        cv2.fillPoly(support, [np.rint(p - [x0, y0]).astype(np.int32)], 255)
        if radius:
            support = cv2.dilate(
                support, np.ones((radius * 2 + 1, radius * 2 + 1), np.uint8)
            )
        xy, uvz, tris = mesh(s)
        local, nfold = raster(xy, uvz, tris, x0, y0, wh, hh)
        folds += nfold
        covered = local[:, :, 0] >= 0
        missing = (support > 0) & ~covered
        if np.any(missing) and np.any(covered):
            _, lab = cv2.distanceTransformWithLabels(
                np.uint8(~covered), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
            )
            lut = np.zeros((lab.max() + 1, 2), np.float32)
            lut[lab[covered]] = local[covered]
            local[missing] = lut[lab[missing]]
            edge_filled += int(missing.sum())
        elif np.any(missing):
            # The tracked surface can be completely outside the picture while its
            # 3-pixel overscan is already visible. Extrapolate only that border sliver.
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            hom = cv2.getPerspectiveTransform(
                np.float32(s["corners"]), np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
            )
            q = cv2.perspectiveTransform(
                np.stack((xx, yy), axis=-1).reshape(1, -1, 2), hom
            ).reshape(hh, wh, 2)
            local[missing] = np.clip(q[missing], 0, 1)
        target = support > 0
        ids[y0:y1, x0:x1][target] = slot
        uv[y0:y1, x0:x1][target] = local[target]
    # Erase only the stage rail/glass marks requested by the user.
    nike = next((i for i, s in enumerate(screens, 1) if s["id"] == "N02_NIKE"), None)
    removal = np.zeros((H, W), np.uint8)
    for obj in fr.get("foreground", []):
        if obj["id"].startswith("stage_"):
            cv2.fillPoly(removal, [np.rint(obj["polygon"]).astype(np.int32)], 255)
    removal = cv2.dilate(removal, np.ones((5, 5), np.uint8))
    if nike:
        matte = np.maximum(matte, removal * (ids == nike))
    missing = (matte > 0) & (ids == 0)
    if np.any(missing):
        _, lab = cv2.distanceTransformWithLabels(
            np.uint8(ids == 0), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
        )
        ilut = np.zeros(lab.max() + 1, np.uint8)
        ulut = np.zeros((lab.max() + 1, 2), np.float32)
        ilut[lab[ids > 0]] = ids[ids > 0]
        ulut[lab[ids > 0]] = uv[ids > 0]
        ids[missing] = ilut[lab[missing]]
        uv[missing] = ulut[lab[missing]]
    return (
        ids,
        np.clip(uv, 0, 1),
        matte,
        {
            "folded_triangles_in_frame": folds,
            "expanded_edge_pixels": edge_filled,
            "screens": len(screens),
        },
    )
