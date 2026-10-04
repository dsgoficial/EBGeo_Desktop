// DOM mínimo para o gerador de símbolos de engenharia do Web (engineering_generator.js e
// engineering_drawing.js) rodar sem navegador. Cobre só o que aqueles dois módulos usam:
// DOMParser e XMLSerializer de SVG, querySelector(All) com tag e [atributo] / [atributo="v"],
// cloneNode, prepend, appendChild, remove, insertAdjacentHTML('beforeend'), dataset, classList,
// textContent, getComputedTextLength e getBBox.
//
// A geometria (getBBox) é calculada aqui, sem traço, como o SVG define: caminho com os extremos
// de curvas e arcos, círculo, elipse, linha, retângulo, polígono. O TEXTO é medido por quem
// hospeda o motor: o Python injeta globalThis.__ebgeoMedidor.medir(texto, familia, tamanho),
// que devolve [advance, tintaEsquerda, tintaDireita, ascent, descent] com QFontMetricsF.
// O Chromium arredonda ascent e descent para pixel inteiro (medido: altura do texto Arial =
// round(0,9053 fs) + round(0,2119 fs) em 10 tamanhos) e une a caixa do advance com a tinta.

const SVG_NS = 'http://www.w3.org/2000/svg';
const G = Function('return this')();

const ENTIDADES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };

function decodificar(s) {
    return s.replace(/&(#x[0-9a-fA-F]+|#\d+|\w+);/g, (m, e) => {
        if (e[0] === '#') return String.fromCodePoint(e[1] === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
        return Object.prototype.hasOwnProperty.call(ENTIDADES, e) ? ENTIDADES[e] : m;
    });
}

function escaparTexto(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escaparAtributo(s) {
    return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

class Texto {
    constructor(dados) {
        this.nodeType = 3;
        this.data = dados;
        this.parentNode = null;
    }
    get textContent() { return this.data; }
    cloneNode() { return new Texto(this.data); }
    remove() { if (this.parentNode) this.parentNode._tirar(this); }
}

function paraCamel(nome) {
    return nome.replace(/-([a-z])/g, (_m, c) => c.toUpperCase());
}

function paraKebab(chave) {
    return 'data-' + chave.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase());
}

// Seletor composto: tag opcional seguida de [attr] ou [attr="valor"]. Vírgula separa alternativas.
function compilarSeletor(seletor) {
    return seletor.split(',').map((parte) => {
        const s = parte.trim();
        const m = s.match(/^([a-zA-Z][\w-]*|\*)?((?:\[[^\]]+\])*)$/);
        if (!m) throw new Error('Seletor não suportado pelo DOM mínimo: ' + s);
        const atributos = [];
        (m[2].match(/\[[^\]]+\]/g) || []).forEach((a) => {
            const r = a.match(/^\[\s*([\w:-]+)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|([^\]\s]+)))?\s*\]$/);
            if (!r) throw new Error('Seletor de atributo não suportado: ' + a);
            const valor = r[2] !== undefined ? r[2] : (r[3] !== undefined ? r[3] : r[4]);
            atributos.push([r[1], valor]);
        });
        const tag = m[1] && m[1] !== '*' ? m[1] : null;
        return (el) => (!tag || el.tagName === tag)
            && atributos.every(([n, v]) => (v === undefined ? el.hasAttribute(n) : el.getAttribute(n) === v));
    });
}

class Elemento {
    constructor(tag, ns) {
        this.nodeType = 1;
        this.tagName = tag;
        this.localName = tag;
        this.nodeName = tag;
        this.namespaceURI = ns || SVG_NS;
        this._atributos = [];
        this.childNodes = [];
        this.parentNode = null;
    }

    // -- atributos ------------------------------------------------------------------------
    getAttribute(nome) {
        const a = this._atributos.find((x) => x[0] === nome);
        return a ? a[1] : null;
    }
    setAttribute(nome, valor) {
        const v = String(valor);
        const a = this._atributos.find((x) => x[0] === nome);
        if (a) a[1] = v; else this._atributos.push([nome, v]);
    }
    removeAttribute(nome) {
        this._atributos = this._atributos.filter((x) => x[0] !== nome);
    }
    hasAttribute(nome) {
        return this._atributos.some((x) => x[0] === nome);
    }
    get id() { return this.getAttribute('id') || ''; }
    set id(v) { this.setAttribute('id', v); }
    get classList() {
        const el = this;
        const lista = () => (el.getAttribute('class') || '').split(/\s+/).filter(Boolean);
        return {
            add: (...nomes) => {
                const atual = lista();
                nomes.forEach((n) => { if (atual.indexOf(n) < 0) atual.push(n); });
                el.setAttribute('class', atual.join(' '));
            },
            remove: (...nomes) => el.setAttribute('class', lista().filter((n) => nomes.indexOf(n) < 0).join(' ')),
            contains: (n) => lista().indexOf(n) >= 0,
        };
    }
    get dataset() {
        const el = this;
        return new Proxy({}, {
            get: (_t, chave) => (typeof chave === 'string' ? (el.getAttribute(paraKebab(chave)) ?? undefined) : undefined),
            set: (_t, chave, valor) => { el.setAttribute(paraKebab(chave), valor); return true; },
            has: (_t, chave) => el.hasAttribute(paraKebab(chave)),
            deleteProperty: (_t, chave) => { el.removeAttribute(paraKebab(chave)); return true; },
            ownKeys: () => el._atributos.filter((a) => a[0].startsWith('data-')).map((a) => paraCamel(a[0].slice(5))),
        });
    }

    // -- árvore ---------------------------------------------------------------------------
    get children() { return this.childNodes.filter((n) => n.nodeType === 1); }
    get firstElementChild() { return this.children[0] || null; }
    get textContent() { return this.childNodes.map((n) => n.textContent).join(''); }
    set textContent(valor) {
        this.childNodes.forEach((n) => { n.parentNode = null; });
        const t = new Texto(String(valor));
        t.parentNode = this;
        this.childNodes = String(valor) === '' ? [] : [t];
    }
    _tirar(no) {
        const i = this.childNodes.indexOf(no);
        if (i >= 0) this.childNodes.splice(i, 1);
        no.parentNode = null;
    }
    appendChild(no) {
        if (no.parentNode) no.parentNode._tirar(no);
        no.parentNode = this;
        this.childNodes.push(no);
        return no;
    }
    prepend(...nos) {
        nos.slice().reverse().forEach((no) => {
            if (no.parentNode) no.parentNode._tirar(no);
            no.parentNode = this;
            this.childNodes.unshift(no);
        });
    }
    remove() { if (this.parentNode) this.parentNode._tirar(this); }
    cloneNode(profundo) {
        const c = new Elemento(this.tagName, this.namespaceURI);
        c._atributos = this._atributos.map((a) => [a[0], a[1]]);
        if (profundo) this.childNodes.forEach((n) => c.appendChild(n.cloneNode(true)));
        return c;
    }
    insertAdjacentHTML(posicao, html) {
        if (posicao !== 'beforeend') throw new Error('insertAdjacentHTML: só beforeend no DOM mínimo');
        analisarFragmento(html, this.namespaceURI).forEach((n) => this.appendChild(n));
    }
    _descendentes(saida) {
        this.children.forEach((c) => { saida.push(c); c._descendentes(saida); });
        return saida;
    }
    querySelectorAll(seletor) {
        const testes = compilarSeletor(seletor);
        return this._descendentes([]).filter((el) => testes.some((t) => t(el)));
    }
    querySelector(seletor) {
        return this.querySelectorAll(seletor)[0] || null;
    }

    // -- geometria ------------------------------------------------------------------------
    getComputedTextLength() {
        return medirTexto(this).advance;
    }
    getBBox() {
        const c = caixa(this);
        return c ? { x: c[0], y: c[1], width: c[2] - c[0], height: c[3] - c[1] } : { x: 0, y: 0, width: 0, height: 0 };
    }
}

// ---------------------------------------------------------------------------------------------
// Análise e serialização de XML
// ---------------------------------------------------------------------------------------------

const TOKEN = /<!--[\s\S]*?-->|<\?[\s\S]*?\?>|<\/([\w:.-]+)\s*>|<([\w:.-]+)((?:\s+[\w:.-]+\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>|([^<]+)/g;
const ATRIBUTO = /([\w:.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;

function analisarFragmento(texto, ns) {
    const raiz = new Elemento('#fragmento', ns);
    const pilha = [raiz];
    let m;
    TOKEN.lastIndex = 0;
    while ((m = TOKEN.exec(texto)) !== null) {
        const topo = pilha[pilha.length - 1];
        if (m[1]) {
            if (pilha.length > 1 && topo.tagName === m[1]) pilha.pop();
            else throw new Error('XML malformado: </' + m[1] + '>');
        } else if (m[2]) {
            const el = new Elemento(m[2], ns);
            let a;
            ATRIBUTO.lastIndex = 0;
            while ((a = ATRIBUTO.exec(m[3] || '')) !== null) {
                el._atributos.push([a[1], decodificar(a[2] !== undefined ? a[2] : a[3])]);
            }
            topo.appendChild(el);
            if (!m[4]) pilha.push(el);
        } else if (m[5] !== undefined) {
            topo.appendChild(new Texto(decodificar(m[5])));
        }
    }
    if (pilha.length !== 1) throw new Error('XML malformado: <' + pilha[pilha.length - 1].tagName + '> sem fechamento');
    const nos = raiz.childNodes.slice();
    nos.forEach((n) => { n.parentNode = null; });
    return nos;
}

function serializar(no) {
    if (no.nodeType === 3) return escaparTexto(no.data);
    const atributos = no._atributos.map(([n, v]) => ' ' + n + '="' + escaparAtributo(v) + '"').join('');
    if (!no.childNodes.length) return '<' + no.tagName + atributos + '/>';
    return '<' + no.tagName + atributos + '>' + no.childNodes.map(serializar).join('') + '</' + no.tagName + '>';
}

class DOMParserMinimo {
    parseFromString(texto) {
        const nos = analisarFragmento(texto, SVG_NS).filter((n) => n.nodeType === 1);
        if (nos.length !== 1) throw new Error('DOMParser: o documento precisa de um único elemento raiz');
        return { documentElement: nos[0] };
    }
}

class XMLSerializerMinimo {
    serializeToString(no) { return serializar(no); }
}

const documentoMinimo = {
    createElementNS: (ns, tag) => new Elemento(tag, ns),
    createElement: (tag) => new Elemento(tag, SVG_NS),
    body: { appendChild: (no) => no, removeChild: (no) => no },
};

// ---------------------------------------------------------------------------------------------
// Medição de texto
// ---------------------------------------------------------------------------------------------

function atributoHerdado(el, nome) {
    for (let e = el; e; e = e.parentNode) {
        const v = e.getAttribute && e.getAttribute(nome);
        if (v !== null && v !== undefined) return v;
    }
    return null;
}

const ASCENT_ARIAL = 1854 / 2048;
const DESCENT_ARIAL = 434 / 2048;

function medirTexto(el) {
    const texto = el.textContent;
    const tamanho = parseFloat(atributoHerdado(el, 'font-size') || '16');
    const familia = (atributoHerdado(el, 'font-family') || 'Arial').split(',')[0].trim().replace(/^['"]|['"]$/g, '');
    const medidor = G.__ebgeoMedidor;
    let r;
    if (medidor && typeof medidor.medir === 'function') {
        r = medidor.medir(texto, familia, tamanho);
        r = [Number(r[0]), Number(r[1]), Number(r[2]), Number(r[3]), Number(r[4])];
    } else {
        // Sem hospedeiro (node, teste): estimativa grosseira, só para não quebrar.
        const w = texto.length * tamanho * 0.556;
        r = [w, 0, w, ASCENT_ARIAL * tamanho, DESCENT_ARIAL * tamanho];
    }
    return { advance: r[0], tintaEsq: r[1], tintaDir: r[2], ascent: Math.round(r[3]), descent: Math.round(r[4]) };
}

// ---------------------------------------------------------------------------------------------
// Caixas geométricas
// ---------------------------------------------------------------------------------------------

function num(el, nome, padrao = 0) {
    const v = parseFloat(el.getAttribute(nome));
    return Number.isFinite(v) ? v : padrao;
}

function unir(a, b) {
    if (!a) return b;
    if (!b) return a;
    return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
}

function caixaDePontos(pts) {
    if (!pts.length) return null;
    let c = [pts[0][0], pts[0][1], pts[0][0], pts[0][1]];
    pts.forEach(([x, y]) => { c = unir(c, [x, y, x, y]); });
    return c;
}

// Extremos de uma quadrática e de uma cúbica num eixo.
function extremosQuad(p0, p1, p2) {
    const d = p0 - 2 * p1 + p2;
    const v = [p0, p2];
    if (d !== 0) {
        const t = (p0 - p1) / d;
        if (t > 0 && t < 1) v.push((1 - t) * (1 - t) * p0 + 2 * (1 - t) * t * p1 + t * t * p2);
    }
    return v;
}

function extremosCub(p0, p1, p2, p3) {
    const v = [p0, p3];
    const a = -p0 + 3 * p1 - 3 * p2 + p3;
    const b = 2 * (p0 - 2 * p1 + p2);
    const c = p1 - p0;
    const raizes = [];
    if (Math.abs(a) < 1e-12) {
        if (Math.abs(b) > 1e-12) raizes.push(-c / b);
    } else {
        const disc = b * b - 4 * a * c;
        if (disc >= 0) {
            const s = Math.sqrt(disc);
            raizes.push((-b + s) / (2 * a), (-b - s) / (2 * a));
        }
    }
    raizes.filter((t) => t > 0 && t < 1).forEach((t) => {
        const u = 1 - t;
        v.push(u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3);
    });
    return v;
}

// Arco elíptico (SVG 1.1, apêndice F.6): pontos extremos do arco percorrido.
function pontosDoArco(x1, y1, rx, ry, rotacao, grande, sentido, x2, y2) {
    if (rx === 0 || ry === 0 || (x1 === x2 && y1 === y2)) return [[x1, y1], [x2, y2]];
    rx = Math.abs(rx);
    ry = Math.abs(ry);
    const phi = rotacao * Math.PI / 180;
    const cp = Math.cos(phi);
    const sp = Math.sin(phi);
    const dx = (x1 - x2) / 2;
    const dy = (y1 - y2) / 2;
    const x1p = cp * dx + sp * dy;
    const y1p = -sp * dx + cp * dy;
    const lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry);
    if (lambda > 1) { rx *= Math.sqrt(lambda); ry *= Math.sqrt(lambda); }
    const num_ = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p;
    const den = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
    let coef = Math.sqrt(Math.max(0, num_ / den));
    if (grande === sentido) coef = -coef;
    const cxp = coef * rx * y1p / ry;
    const cyp = -coef * ry * x1p / rx;
    const cx = cp * cxp - sp * cyp + (x1 + x2) / 2;
    const cy = sp * cxp + cp * cyp + (y1 + y2) / 2;
    const ang = (ux, uy, vx, vy) => {
        const a = Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
        return a;
    };
    const t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry);
    let dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry);
    if (!sentido && dt > 0) dt -= 2 * Math.PI;
    if (sentido && dt < 0) dt += 2 * Math.PI;
    const ponto = (t) => [cx + rx * Math.cos(t) * cp - ry * Math.sin(t) * sp, cy + rx * Math.cos(t) * sp + ry * Math.sin(t) * cp];
    const pts = [[x1, y1], [x2, y2]];
    // Ângulos em que x ou y têm derivada nula.
    const tx = Math.atan2(-ry * sp, rx * cp);
    const ty = Math.atan2(ry * cp, rx * sp);
    [tx, tx + Math.PI, ty, ty + Math.PI].forEach((t) => {
        let rel = (t - t1) / dt;
        // Normaliza t para dentro da volta percorrida.
        for (let k = -2; k <= 2; k++) {
            rel = (t + 2 * Math.PI * k - t1) / dt;
            if (rel > 0 && rel < 1) { pts.push(ponto(t + 2 * Math.PI * k)); break; }
        }
    });
    return pts;
}

function caixaDoCaminho(d) {
    const tokens = (d || '').match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g) || [];
    const pts = [];
    let i = 0;
    let cmd = null;
    let x = 0, y = 0, x0 = 0, y0 = 0;
    let ctrl = null;
    let ctrlQ = null;
    const n = () => parseFloat(tokens[i++]);
    while (i < tokens.length) {
        if (/[a-zA-Z]/.test(tokens[i])) cmd = tokens[i++];
        if (!cmd) break;
        const rel = cmd === cmd.toLowerCase();
        const C = cmd.toUpperCase();
        const bx = rel ? x : 0;
        const by = rel ? y : 0;
        if (C === 'Z') {
            x = x0; y = y0; ctrl = ctrlQ = null;
            pts.push([x, y]);
            continue;
        }
        if (C === 'M') {
            x = bx + n(); y = by + n(); x0 = x; y0 = y; pts.push([x, y]);
            cmd = rel ? 'l' : 'L';
            ctrl = ctrlQ = null;
        } else if (C === 'L') {
            x = bx + n(); y = by + n(); pts.push([x, y]); ctrl = ctrlQ = null;
        } else if (C === 'H') {
            x = bx + n(); pts.push([x, y]); ctrl = ctrlQ = null;
        } else if (C === 'V') {
            y = by + n(); pts.push([x, y]); ctrl = ctrlQ = null;
        } else if (C === 'C' || C === 'S') {
            let c1x, c1y;
            if (C === 'C') { c1x = bx + n(); c1y = by + n(); } else {
                c1x = ctrl ? 2 * x - ctrl[0] : x; c1y = ctrl ? 2 * y - ctrl[1] : y;
            }
            const c2x = bx + n(), c2y = by + n(), ex = bx + n(), ey = by + n();
            const xs = extremosCub(x, c1x, c2x, ex);
            const ys = extremosCub(y, c1y, c2y, ey);
            xs.forEach((v) => pts.push([v, ey]));
            ys.forEach((v) => pts.push([ex, v]));
            ctrl = [c2x, c2y]; ctrlQ = null; x = ex; y = ey;
        } else if (C === 'Q' || C === 'T') {
            let qx, qy;
            if (C === 'Q') { qx = bx + n(); qy = by + n(); } else {
                qx = ctrlQ ? 2 * x - ctrlQ[0] : x; qy = ctrlQ ? 2 * y - ctrlQ[1] : y;
            }
            const ex = bx + n(), ey = by + n();
            extremosQuad(x, qx, ex).forEach((v) => pts.push([v, ey]));
            extremosQuad(y, qy, ey).forEach((v) => pts.push([ex, v]));
            ctrlQ = [qx, qy]; ctrl = null; x = ex; y = ey;
        } else if (C === 'A') {
            const rx = n(), ry = n(), rot = n(), grande = n(), sentido = n();
            const ex = bx + n(), ey = by + n();
            pontosDoArco(x, y, rx, ry, rot, grande ? 1 : 0, sentido ? 1 : 0, ex, ey).forEach((p) => pts.push(p));
            x = ex; y = ey; ctrl = ctrlQ = null;
        } else {
            throw new Error('Comando de caminho não suportado: ' + cmd);
        }
    }
    // Caixa dos pontos: os eixos foram tratados separadamente, então só vale o min/max por eixo.
    return caixaDePontos(pts);
}

const NAO_DESENHAM = ['defs', 'pattern', 'clipPath', 'mask', 'marker', 'symbol', 'linearGradient', 'radialGradient',
    'title', 'desc', 'metadata', 'style'];

function aplicarTransformacao(el, c) {
    const t = el.getAttribute && el.getAttribute('transform');
    if (!c || !t) return c;
    let m = [1, 0, 0, 1, 0, 0];
    const mult = (a, b) => [a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3],
        a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5]];
    (t.match(/\w+\s*\([^)]*\)/g) || []).forEach((f) => {
        const nome = f.match(/^\w+/)[0];
        const v = (f.match(/[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g) || []).map(Number);
        let k = [1, 0, 0, 1, 0, 0];
        if (nome === 'translate') k = [1, 0, 0, 1, v[0], v[1] || 0];
        else if (nome === 'scale') k = [v[0], 0, 0, v.length > 1 ? v[1] : v[0], 0, 0];
        else if (nome === 'matrix') k = v;
        else if (nome === 'rotate') {
            const a = v[0] * Math.PI / 180, cx = v[1] || 0, cy = v[2] || 0;
            k = mult(mult([1, 0, 0, 1, cx, cy], [Math.cos(a), Math.sin(a), -Math.sin(a), Math.cos(a), 0, 0]), [1, 0, 0, 1, -cx, -cy]);
        }
        m = mult(m, k);
    });
    const p = [[c[0], c[1]], [c[2], c[1]], [c[0], c[3]], [c[2], c[3]]].map(([x, y]) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]);
    return caixaDePontos(p);
}

function caixaPropria(el) {
    switch (el.tagName) {
    case 'g':
    case 'svg':
    case 'a':
        return el.children.reduce((acc, f) => unir(acc, aplicarTransformacao(f, caixaPropria(f))), null);
    case 'path':
        return caixaDoCaminho(el.getAttribute('d'));
    case 'line':
        return caixaDePontos([[num(el, 'x1'), num(el, 'y1')], [num(el, 'x2'), num(el, 'y2')]]);
    case 'circle': {
        const cx = num(el, 'cx'), cy = num(el, 'cy'), r = num(el, 'r');
        return [cx - r, cy - r, cx + r, cy + r];
    }
    case 'ellipse': {
        const cx = num(el, 'cx'), cy = num(el, 'cy'), rx = num(el, 'rx'), ry = num(el, 'ry');
        return [cx - rx, cy - ry, cx + rx, cy + ry];
    }
    case 'rect': {
        const x = num(el, 'x'), y = num(el, 'y');
        return [x, y, x + num(el, 'width'), y + num(el, 'height')];
    }
    case 'polygon':
    case 'polyline': {
        const v = (el.getAttribute('points') || '').match(/[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g) || [];
        const pts = [];
        for (let k = 0; k + 1 < v.length; k += 2) pts.push([Number(v[k]), Number(v[k + 1])]);
        return caixaDePontos(pts);
    }
    case 'text': {
        if (!el.textContent) return null;  // o Chromium deixa texto vazio fora da união
        const m = medirTexto(el);
        const x = num(el, 'x');
        const y = num(el, 'y');
        const ancora = atributoHerdado(el, 'text-anchor') || 'start';
        const inicio = ancora === 'middle' ? x - m.advance / 2 : (ancora === 'end' ? x - m.advance : x);
        const esq = Math.min(inicio, inicio + m.tintaEsq);
        const dir = Math.max(inicio + m.advance, inicio + m.tintaDir);
        return [esq, y - m.ascent, dir, y + m.descent];
    }
    default:
        // defs, pattern, marcadores e afins não entram na caixa (NAO_DESENHAM); elemento
        // desconhecido também não, para a caixa nunca crescer por algo que não se sabe medir.
        if (NAO_DESENHAM.indexOf(el.tagName) < 0) {
            G.console && G.console.warn && G.console.warn('getBBox: elemento sem caixa no DOM mínimo: ' + el.tagName);
        }
        return null;
    }
}

function caixa(el) {
    return caixaPropria(el);
}

// Instala DOMParser, XMLSerializer e document só durante a chamada ao gerador de engenharia e
// devolve a função que desfaz: o milsymbol, no mesmo motor, não pode ver um document falso.
export function instalarDomTemporario() {
    const antes = { DOMParser: G.DOMParser, XMLSerializer: G.XMLSerializer, document: G.document };
    G.DOMParser = DOMParserMinimo;
    G.XMLSerializer = XMLSerializerMinimo;
    G.document = documentoMinimo;
    return () => {
        Object.keys(antes).forEach((k) => {
            if (antes[k] === undefined) delete G[k]; else G[k] = antes[k];
        });
    };
}

export { DOMParserMinimo, XMLSerializerMinimo, documentoMinimo, caixaDoCaminho, Elemento };
