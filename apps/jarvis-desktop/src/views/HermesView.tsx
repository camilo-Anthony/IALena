import React, { useState, useEffect } from "react";
import { jarvisAPI } from "../hooks/useJarvisAPI";
import type { HermesMCP, HermesToolsets } from "../types";

export function HermesView() {
  const [mcps, setMcps] = useState<HermesMCP[]>([]);
  const [toolsets, setToolsets] = useState<HermesToolsets | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadHermesData() {
      try {
        setLoading(true);
        const [mcpRes, toolsetsRes] = await Promise.all([
          jarvisAPI.getHermesMCPs(),
          jarvisAPI.getHermesToolsets(),
        ]);
        setMcps(mcpRes.mcps || []);
        setToolsets(toolsetsRes);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    }
    loadHermesData();
  }, []);

  return (
    <div className="w-full h-full flex flex-col bg-[#020710] border border-cyan-500/20 rounded-lg overflow-hidden text-[#e0f4ff] font-sans p-5">
      {/* Cabecera de la vista */}
      <div className="border-b border-cyan-500/20 pb-3 mb-4 shrink-0 flex justify-between items-center">
        <div>
          <h2 className="text-base font-mono font-bold tracking-wider text-cyan-400">VISTA DETALLADA DE HERMES</h2>
          <p className="text-xs text-slate-400 mt-1">
            Visualización segura y de solo lectura de MCPs, herramientas y configuraciones del cerebro agéntico.
          </p>
        </div>
        <div className="bg-slate-900 border border-cyan-500/20 text-[10px] font-mono rounded px-2.5 py-1 text-cyan-300">
          EXTERNAL CONF
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-xs font-mono text-cyan-400">
          Cargando datos del cerebro de Hermes...
        </div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-xs font-mono text-red-400">
          Error al cargar: {error}
        </div>
      ) : (
        <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6 overflow-y-auto min-h-0 pr-2">
          {/* Columna MCP Servers */}
          <div className="space-y-4">
            <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4 h-full flex flex-col">
              <h3 className="text-xs font-mono text-cyan-400 tracking-wider mb-3 uppercase border-b border-cyan-500/10 pb-1.5 shrink-0">
                MCP Servers Configurados
              </h3>
              <div className="flex-1 overflow-y-auto space-y-3 min-h-0 pr-1">
                {mcps.length === 0 ? (
                  <div className="text-xs text-slate-500 italic">No hay MCP servers detectados en ~/.hermes/config.yaml</div>
                ) : (
                  mcps.map((mcp, idx) => (
                    <div key={idx} className="bg-slate-900/60 border border-cyan-500/5 p-3 rounded space-y-1">
                      <div className="text-xs font-mono font-bold text-cyan-200">{mcp.name}</div>
                      {mcp.command && (
                        <div className="text-[10px] font-mono text-slate-400 truncate">
                          Comando: <span className="text-slate-300">{mcp.command} {mcp.args.join(" ")}</span>
                        </div>
                      )}
                      {mcp.url && (
                        <div className="text-[10px] font-mono text-slate-400 truncate">
                          URL: <span className="text-slate-300">{mcp.url}</span>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Columna Toolsets habilitados */}
          <div className="space-y-4">
            <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4 h-full flex flex-col">
              <h3 className="text-xs font-mono text-cyan-400 tracking-wider mb-3 uppercase border-b border-cyan-500/10 pb-1.5 shrink-0">
                Toolsets Activos
              </h3>
              <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-1">
                <div>
                  <div className="text-[10px] font-mono text-slate-400 mb-1.5">HABILITADOS:</div>
                  {toolsets?.enabled && toolsets.enabled.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {toolsets.enabled.map((t) => (
                        <span key={t} className="bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-[10px] font-mono px-2 py-0.5 rounded">
                          {t}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 italic">Ningún toolset habilitado explícitamente</div>
                  )}
                </div>

                <div>
                  <div className="text-[10px] font-mono text-slate-400 mb-1.5">DESHABILITADOS:</div>
                  {toolsets?.disabled && toolsets.disabled.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {toolsets.disabled.map((t) => (
                        <span key={t} className="bg-red-500/5 border border-red-500/20 text-red-300/80 text-[10px] font-mono px-2 py-0.5 rounded">
                          {t}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 italic">Ningún toolset deshabilitado explícitamente</div>
                  )}
                </div>

                <div className="text-[10px] font-mono text-slate-500 border-t border-cyan-500/5 pt-3">
                  Plataforma de ejecución: <span className="text-slate-400 uppercase">{toolsets?.platform || "default"}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
