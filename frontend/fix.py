import sys
with open('src/componunts/scrapper/ZeptoScrapper.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = lines[:429]

clean_ending = """        {/* Right Side: Log Console Terminal */}
        <div className="lg:col-span-7 flex flex-col">
          <Card className="shadow-lg border border-blue-gray-100 flex-1 flex flex-col bg-gray-900 text-white rounded-xl overflow-hidden h-[520px] min-h-[520px] max-h-[520px]">
            <div className="bg-gray-800 px-4 py-3 flex justify-between items-center border-b border-gray-700 flex-shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <Typography className="text-xs text-gray-400 font-bold ml-2 font-mono">
                  zepto-scraper-background@logs
                </Typography>
              </div>
              <div className="bg-gray-900 text-[10px] px-2 py-0.5 rounded font-mono text-deep-purple-400 border border-deep-purple-500/20">
                {statusInfo.status.toUpperCase()}
              </div>
            </div>

            {/* Terminal Logs Screen */}
            <div className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-2 no-scrollbar">
              {logs.length === 0 ? (
                <div className="text-gray-500 italic h-full flex items-center justify-center">
                  Terminal inactive. Start Zepto scrape to watch live execution logs.
                </div>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} className="leading-relaxed flex items-start gap-2">
                    <span className="text-gray-500 select-none">[{log.timestamp}]</span>
                    <span
                      className={
                        log.level === "ERROR" || log.type === "error"
                          ? "text-red-400 font-bold"
                          : log.level === "WARNING" || log.type === "warning"
                          ? "text-yellow-400"
                          : log.type === "success" || log.message?.includes("successfully")
                          ? "text-green-400"
                          : log.type === "system"
                          ? "text-blue-400 font-bold"
                          : "text-gray-200"
                      }
                    >
                      {log.message}
                    </span>
                  </div>
                ))
              )}
              <div ref={terminalEndRef} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ZeptoScrapper;
"""

with open('src/componunts/scrapper/ZeptoScrapper.jsx', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
    f.write(clean_ending)
