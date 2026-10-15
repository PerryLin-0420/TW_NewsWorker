# 全文判斷 vs 舊標註（審閱用）

`final_label` 請在 fulltext_truth.json 填 1 或 0；留空代表採用全文判斷。

| # | 全文真值 | 舊標註 | 一致 | 信心 | 來源 | 標題 | 理由 | 網址 |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 0(hand) | ✗ | 高 | CNBC Finance | All U.S. bombers leave UK air base on concerns of suspected  | 荷莫茲海峽油輪遇襲，牽動原油供應 | https://www.cnbc.com/2026/10/04/more-tankers-struck-in-gulf-waters-as-iran-reiterates-conditions.html |
| 2 | 0 | 0(hand) | ✓ | 高 | CNBC Finance | Sports betting is increasingly the norm for Gen Z.  Here’s w | Z世代運彩趨勢屬社會消費議題 | https://www.cnbc.com/2026/10/04/gen-z-sports-betting-financial-and-mental-health-risks.html |
| 3 | 0 | 1(hand) | ✗ | 中 | CNBC Finance | A 'weird' IPO pull, a tainted reputation and the stalled bre | 主軸為穿戴產品與隱私爭議 | https://www.cnbc.com/2026/10/04/ai-wearables-oura-ipo-privacy.html |
| 4 | 0 | 0(hand) | ✓ | 高 | CNBC Finance | Starting a watch collection? What beginners should know befo | 手錶收藏入門屬生活消費 | https://www.cnbc.com/2026/10/04/watch-collecting-beginners.html |
| 5 | 0 | 1(hand) | ✗ | 中 | CNBC Finance | Chick-fil-A wants to stay a family business even as it expan | 企業概況專訪，無具體經濟事件 | https://www.cnbc.com/2026/10/04/chick-fil-a-ceo-andrew-cathy-family-ownership-growth.html |
| 6 | 0 | 0(hand) | ✓ | 高 | Guardian Business | Money stolen by scammers hijacking UK social media accounts  | 詐騙犯罪新聞 | https://www.theguardian.com/money/2026/oct/05/scammers-hijacking-uk-social-media-accounts |
| 7 | 0 | 0(hand) | ✓ | 中 | Guardian Business | Tories to pledge to scrap Environment Agency and Natural Eng | 在野黨政見承諾，非實際政策 | https://www.theguardian.com/politics/2026/oct/04/tories-scrap-environment-agency-natural-england-conservative-conference |
| 8 | 1 | 1(hand) | ✓ | 高 | DW Business | Germany's car crisis: Can the 35-hour workweek survive? | 德車業裁員與成本危機衝擊產業 | https://www.dw.com/en/germany-s-car-crisis-can-the-35-hour-workweek-survive/a-79307488?maca=en-rss-en-bus-2091-rdf |
| 9 | 0 | 0(hand) | ✓ | 高 | DW Business | Global Gender Gap Report: Women's hard-won gains 'fragile' | 性別平等報告屬社會議題 | https://www.dw.com/en/global-gender-gap-report-women-s-hard-won-gains-fragile/a-79280086?maca=en-rss-en-bus-2091-rdf |
| 10 | 1 | 1(hand) | ✓ | 高 | DW Business | Can Iran replace sea trade with land routes? | 封鎖下伊朗貿易路線轉移 | https://www.dw.com/en/can-iran-replace-sea-trade-with-land-routes/a-79211179?maca=en-rss-en-bus-2091-rdf |
| 11 | 1 | 0(hand) | ✗ | 中 | Nikkei Asia | Takaichi policy speech, Malaysia budget, Pacific islands cli | 日本減稅法案與馬來西亞預算政策 | https://asia.nikkei.com/spotlight/your-week-in-asia/takaichi-policy-speech-malaysia-budget-pacific-islands-climate-summit |
| 12 | 1 | 0(hand) | ✗ | 中 | Nikkei Asia | Nitori tackles Japan's furniture waste with giant recycling  | 建國內回收供應鏈，年省逾億日圓成本 | https://asia.nikkei.com/business/consumer/nitori-tackles-japan-s-furniture-waste-with-giant-recycling-center |
| 13 | 0 | 0(hand) | ✓ | 中 | Nikkei Asia | Airbnb unlikely to let AI agents like Muse make bookings, CE | CEO表態屬企業策略評論，無具體影響 | https://asia.nikkei.com/business/travel-leisure/airbnb-unlikely-to-let-ai-agents-like-muse-make-bookings-ceo-says |
| 14 | 1 | 0(hand) | ✗ | 中 | Nikkei Asia | Roadblocks in Pakistan capital to deter Imran Khan supporter | 封路阻斷供應鏈並衝擊當地商業 | https://asia.nikkei.com/politics/roadblocks-in-pakistan-capital-to-deter-imran-khan-supporters |
| 15 | 1 | 1(hand) | ✓ | 高 | KED Global | BOK holds fire amid Iran war uncertainty; outgoing Gov. Rhee | 韓國央行利率決策與匯率通膨展望 | https://www.kedglobal.com/central-bank/newsView/ked202604100001 |
| 16 | 0 | 0(hand) | ✓ | 高 | SCMP Business | 140 Years of Everyday Moments | 企業週年廣編稿，無經濟事件 | https://www.scmp.com/presented/business/topics/c-suite-content-hub/article/3369345/140-years-everyday-moments?utm_source=rss_feed |
| 17 | 0 | 1(hand) | ✗ | 高 | SCMP Business | LIM Advisors founder George Long: ‘We’ve been here 30 years. | 投資人專訪廣編稿，屬人物報導 | https://www.scmp.com/presented/business/topics/playing-long-game/article/3369280/lim-advisors-founder-george-long-weve-been-here-30-years-were-going-be-around?utm_source=rss_feed |
| 18 | 1 | 1(hand) | ✓ | 高 | Business Times SG | Yemen’s Houthis say they attacked Aramco facility in Riyadh  | 沙烏地阿美能源設施遭攻擊牽動油市 | https://www.businesstimes.com.sg/international/yemens-houthis-say-they-attacked-aramco-facility-riyadh-missiles-drones |
| 19 | 1 | 1(hand) | ✓ | 中 | Yahoo奇摩財經 | 美司法部不重啟鮑威爾刑事調查，獨立審計仍留後續追查空間 | 涉Fed獨立性，文中點出市場關注 | https://tw.stock.yahoo.com/news/%E7%BE%8E%E5%8F%B8%E6%B3%95%E9%83%A8%E4%B8%8D%E9%87%8D%E5%95%9F%E9%AE%91%E5%A8%81%E7%88%BE%E5%88%91%E4%BA%8B%E8%AA%BF%E6%9F%A5-%E7%8D%A8%E7%AB%8B%E5%AF%A9%E8%A8%88%E4%BB%8D%E7%95%99%E5%BE%8C%E7%BA%8C%E8%BF%BD%E6%9F%A5%E7%A9%BA%E9%96%93-234712549.html |
| 20 | 0 | 0(hand) | ✓ | 高 | Yahoo奇摩財經 | 蘋果確認iPhone 18 Pro Max遇AT&T網路故障問題，受影響用戶需換機 | 單一產品故障新聞 | https://tw.stock.yahoo.com/news/%E8%98%8B%E6%9E%9C%E7%A2%BA%E8%AA%8Diphone-18-pro-max%E9%81%87at-t%E7%B6%B2%E8%B7%AF%E6%95%85%E9%9A%9C%E5%95%8F%E9%A1%8C-234318507.html |
| 21 | 0 | 0(hand) | ✓ | 中 | Yahoo奇摩財經 | 川普擬任命Clayton出任AI沙皇，續掌18個情報機構 | 人事任命，未有具體政策影響 | https://tw.stock.yahoo.com/news/%E5%B7%9D%E6%99%AE%E6%93%AC%E4%BB%BB%E5%91%BDclayton%E5%87%BA%E4%BB%BBai%E6%B2%99%E7%9A%87-%E7%BA%8C%E6%8E%8C18%E5%80%8B%E6%83%85%E5%A0%B1%E6%A9%9F%E6%A7%8B-234241288.html |
| 22 | 1 | 0(hand) | ✗ | 中 | 經濟日報 產業 | 資策會數位轉型研究院主任楊惠雯：人才供給 建新模式 | 連鎖業缺工迫使縮短營業時間 | https://money.udn.com/money/story/10871/9794223 |
| 23 | 0 | 0(hand) | ✓ | 高 | 經濟日報 產業 | Grab 集團營運董事總經理余偉騰：數位店面 帶動成長 | 行銷案例演講，無具體經濟影響 | https://money.udn.com/money/story/10871/9794226 |
| 24 | 0 | 0(hand) | ✓ | 中 | 經濟日報 產業 | 未來流通研究所總監林原慶：虛擬店長 提升效率 | 論壇演講談產業趨勢，非事件性新聞 | https://money.udn.com/money/story/10871/9794227 |
| 25 | 0 | 0(hand) | ✓ | 高 | 經濟日報 產業 | 王品集團董事總經理英美惠：品牌布局 重稀缺性 | 企業品牌策略分享，屬經營心法 | https://money.udn.com/money/story/10871/9794229 |
| 26 | 0 | 0(hand) | ✓ | 高 | 經濟日報 產業 | 曼都集團董事長賴淑芬：跨界發展 超前部署 | 企業轉型經驗分享，無市場影響 | https://money.udn.com/money/story/10871/9794230 |
| 27 | 0 | 0(hand) | ✓ | 低 | SCMP Business | Temu took the world by storm – but has the shopping app lost | 專題回顧，全文未見具體監管衝擊 | https://www.scmp.com/tech/big-tech/article/3369595/temu-took-world-storm-has-shopping-app-lost-its-thunder?utm_source=rss_feed |
| 28 | 1 | 1(claude) | ✓ | 高 | CNBC World Economy | The 2029 tipping point: Western populations are about to sta | 穆迪示警人口老化衝擊財政與成長 | https://www.cnbc.com/2026/10/05/aging-population-moodys-public-finances.html |
| 29 | 0 | 1(claude) | ✗ | 中 | 經濟日報 產業 | 川普新任命帶動 AI 政策轉向安全管控 台廠看好 AI 資安需求升溫 | 人事任命，受惠推論屬法人臆測 | https://money.udn.com/money/story/5612/9795544 |
| 30 | 0 | 1(claude) | ✗ | 中 | 中央社 財經 | Reflection首款開放權重模型　恐對美中AI對手構威脅 | AI產品發布新聞，市場影響不具體 | https://www.cna.com.tw/news/aopl/202610050295.aspx |
| 31 | 0 | 1(claude) | ✗ | 高 | Mining.com | Colorado summit video: Giustra says gold rally is missing re | 個人看法訪談，屬評論 | https://www.mining.com/colorado-summit-video-giustra-says-gold-rally-is-missing-retail/ |
| 32 | 0 | 1(claude) | ✗ | 中 | Yahoo奇摩財經 | 葉倫批評川普對待盟友方式，支持各國反制美國關稅 | 前官員評論，無新政策或措施 | https://tw.stock.yahoo.com/news/%E8%91%89%E5%80%AB%E6%89%B9%E8%A9%95%E5%B7%9D%E6%99%AE%E5%B0%8D%E5%BE%85%E7%9B%9F%E5%8F%8B%E6%96%B9%E5%BC%8F-%E6%94%AF%E6%8C%81%E5%90%84%E5%9C%8B%E5%8F%8D%E5%88%B6%E7%BE%8E%E5%9C%8B%E9%97%9C%E7%A8%85-234208478.html |
| 33 | 0 | 1(claude) | ✗ | 高 | Guardian Business | Ikea to pilot online buyback service for secondhand furnitur | 零售商服務試辦，屬產品新聞 | https://www.theguardian.com/business/2026/oct/07/ikea-to-pilot-online-buyback-service-for-secondhand-furniture |