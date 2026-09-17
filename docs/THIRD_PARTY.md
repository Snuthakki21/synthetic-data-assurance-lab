# Third-party assets

Original application Python/JavaScript, fixtures and documentation are licensed under the root MIT license by Seshu Nuthakki. Bundled third-party files are not relicensed by that statement.

The browser runtime in web/vendor/pyodide/ comes from the [Pyodide project](https://github.com/pyodide/pyodide). Its retained LICENSE is Mozilla Public License 2.0. The distribution contains CPython/WebAssembly and related compiled runtime assets with their upstream notices; see the [Pyodide source and licensing documentation](https://github.com/pyodide/pyodide) for corresponding sources. The local pyodide-lock.json records the runtime ABI, Python version and package checksums supplied by that distribution. It lists a package catalog, not proof that all listed packages are bundled or loaded.

Preserve these notices and verify upstream licensing when redistributing or updating the runtime. Python's standard library is supplied by the operator's Python installation for local execution. Coverage is a pinned development dependency; GitHub Actions run pinned upstream commits listed in ACTION_PINS.md.

The bundled distribution is Pyodide 314.0.7, using CPython 3.14.2 according to its lock metadata. `web/vendor/pyodide/CPYTHON-LICENSE.txt` retains the license from the [CPython v3.14.2 source](https://github.com/python/cpython/blob/v3.14.2/LICENSE). `web/vendor/pyodide/SHA256SUMS.json` records locally computed SHA-256 hashes for the included runtime assets; these identify the bundled bytes, not an independent security attestation. The distribution assets were obtained from the [official Pyodide CDN](https://cdn.jsdelivr.net/pyodide/v314.0.7/full/).
