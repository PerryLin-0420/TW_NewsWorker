# 正負評價標註（Claude 盲判，待人工抽查）

在 sentiment_labels.json 對應項目加 `"human": "正面/負面/中性"` 即可覆蓋。

| # | 評價 | 信心 | 標題 | 摘要（前 120 字） |
|---|---|---|---|---|
| 1 | 正面 | 中 | 數發部百億AI投資方案　開放主要營運在台境外公司可納投 | 數發部去年啟動「加強投資AI新創實施方案」，截至今年8月底已投資10家AI新創及數位經濟相關企業，投入約新台幣2.55億元，帶動約5.7億元民間投資。數發部近期修正作業要點，放寬可投資於台灣境內執行主要營業活動的境外公司，盼擴大扶植範圍。 |
| 2 | 正面 | 高 | 海悅9月營收14.81億元、年增96.3%，指標建案陸續啟動，Q4代銷收入可期 | 【財訊快報／記者張家瑋報導】代銷商海悅(2348)公告9月合併營收14.81億元，月增3.93%、年增96.3%；累計前9月合併營收81億元、年增率83.29%。海悅表示，9月營收增加，主要係新北市中和區「寶亞世界公館」、「大同新紀元」、永 |
| 3 | 負面 | 高 | Diesel prices are surging putting further pressure on Europe | Trucks, farms and industry are powered with diesel. Now prices are soaring due to refinery disruptions, supply shortages |
| 4 | 中性 | 中 | 成本壓力難擋家電業迎漲價 業者瞄準2027年新能效標準搶攻換機商機 | 銅、塑膠粒與物流運費齊漲，聲寶、燦坤指家電將掀漲價潮，冰箱、洗衣機約漲3%至5%，液晶電視成本反映最明顯。&#10;經濟部修訂冰箱能源效率制度，2027年門檻大幅提高；燦坤推一級能效冰箱、洗衣機8折起，搭配最高5000元補助。&#10;家電 |
| 5 | 正面 | 高 | 美科技股走揚、台積電ADR漲近3%　法人：台股拚量增續攻 | 美股收紅，台積電美國存託憑證（ADR）走揚2.96%，台指期夜盤大漲677點。法人指出，美國就業數據降溫，舒緩市場對緊縮... |
| 6 | 正面 | 中 | Higher-for-longer rates create opening for private real estate debt: D | At the start of 2026, investors expected interest rates in the UK and Europe to ease, providing another lift to a tentat |
| 7 | 負面 | 中 | Balancing a decarbonizing power system: Aurora Energy Research | The Iran war represents the second commodities price shock in five year.The narrative that heightened geopolitical tensi |
| 8 | 正面 | 高 | 輝達鴻海合作自動化機器人組裝　提升GB300成功率 | 人工智慧AI晶片大廠輝達（NVIDIA）近日在技術部落格，分享與鴻海合作使用機器人製造機器成果，輝達指出，NVIDIA GB300匯流排母線（Busbar）及多組連接器等較複雜、仰賴人工的製程，導入機器人自動化，提升組裝穩定性與效率。 |
| 9 | 正面 | 高 | Korean shipbuilders sweep up LNG, ammonia orders as energy demand hold | South Korea&rsquo;s top shipbuilders are capitalizing on resilient demand for energy infrastructure, landing a string of |
| 10 | 正面 | 中 | 31檔10月除息台股ETF搶先看，包括00927在內4檔年化配息率飆破20% | 【財訊快報／記者劉居全報導】10月開盤以來大盤大漲頻創新高，台股ETF也持續發熱，不過在高檔之際，穩健保守投資人更青睞有不錯的配息金額及年化殖利率數據的高息ETF。根據CMONEY統計已公告10月份將除息的台股ETF有31檔，共有37312 |
| 11 | 正面 | 中 | BT to buy broadband supplier TalkTalk in £400m rescue deal, saving 900 | Virgin Media O2 complains of ‘stitch-up’ over rival provider, which has 1.5m customers |
| 12 | 負面 | 高 | Euro hits 17-month low, dollar near pre-Liberation Day highs | THE euro slid to a 17-month low against the US dollar on Monday (Oct 5), as concerns about France’s ability to rein in i |
| 13 | 負面 | 高 | How Volkswagen's huge workforce became a costly burden | The struggling German carmaker plans to cut up to 100,000 jobs from its 630,000-strong workforce. How did VW's headcount |
| 14 | 正面 | 高 | 美版 DeepSeek 搶市 新創 Reflection 將推開放權重模型 可望帶旺台鏈 | 輝達（NVIDIA）投資有「美國版DeepSeek」之稱的AI新創Reflection，近期將推出首款開放權重模型（Open-Weight Model），主打以高性價比與優異效能，提供企業整套「AI工廠」落地解決方案，被視為美國在開源AI領 |
| 15 | 正面 | 低 | Bessent downplays worries on rising US Treasury yields, AI bubble conc | He argues that ripple effects of the Iran war are masking underlying US economic strength Read more at The Business Time |
| 16 | 正面 | 中 | Reflection AI boosts US ambition to compete with Chinese ‘open’ models | Start-up claims new model Beam is on par with leading Chinese competitor as battle with Beijing intensifies |
| 17 | 中性 | 中 | China's BYD to sell mini-EV meant for Japan in other markets | Model designed to meet Japanese 'kei' specs to debut in Macao, Sri Lanka |
| 18 | 正面 | 高 | Nippon Paint clinches Dulux brand with deal for Akzo Nobel's Southeast | Asian market leader sees takeover of Dutch group's regional operations leading to faster earnings growth |
| 19 | 中性 | 高 | For global property investors, real test comes after acquisition: exec | Cross-border real estate is often won or lost after the deal closes.A transaction may be approved in Seoul, London or Si |
| 20 | 負面 | 高 | Standard Chartered Says Hormuz Oil Flows Are Far From Normal | Exporters have adapted through pipelines, bypass ports and extensive ship-to-ship transfers, but the system is more expe |
| 21 | 中性 | 中 | Trump defers diesel tax for truckers as fuel costs bite weeks before U | US President Donald Trump has signed an executive order deferring tax payments on red-dyed diesel used on public roads,  |
| 22 | 正面 | 高 | Malaysia's Top Glove triples net profit despite high material costs | World's largest rubber glove maker plans to increase production amid high demand |
| 23 | 中性 | 中 | Salesforce shares sit at the epicenter of AI confusion. Here's how to  | If ever there was a stock that personified the promise and peril of the AI trade, it's Salesforce. |
| 24 | 中性 | 中 | CEA主席藉新數據質疑9月升息，暗示Fed 10月應按兵不動 | 【財訊快報／陳孟朔】外電報導，白宮經濟顧問委員會(CEA)主席米蘭(Stephen Miran)上週五(2日)表示，從最新公布的就業與通膨數據回頭檢視，聯準會(Fed)9月升息缺乏充分合理性，並認為美國通膨回落速度已經足夠快。他的表態並非單 |
| 25 | 正面 | 高 | Japan's Rapidus to help 17 companies design chips for clients | Partnership with Toshiba, others seen boosting ability to supply advanced semiconductors |
| 26 | 負面 | 中 | Oil climbs after Yemeni Houthis attack Saudi Aramco sites | Brent crude futures inched up 5 cents to US$102.30 a barrel at 0900 GMT Read more at The Business Times. |
| 27 | 正面 | 中 | Japan's Aozora, Arthur D. Little partner on investment, advisory servi | Joint venture aims to help small, mid-sized companies grow and pursue M&A |
| 28 | 正面 | 中 | Hana Financial Group opens new Incheon HQ, bets on closer finance-tech | Hana Financial Group has announced the completion of its Hana Financial Town project in Cheongna, Incheon, with the open |
| 29 | 中性 | 高 | OPEC+召開會議　同意維持11月石油產量目標不變 | 石油輸出國組織與夥伴國（OPEC+）今天指出，已經同意維持11月石油產量目標不變，這跟市場預期相符，即是明年之前不太可能有進一步的產量政策調整。 |
| 30 | 正面 | 高 | 〈台股風向球〉營收和法說會重頭戲陸續上演 加熱光輝10月行情 | 台股上周續彈451點，穩在48000點上墊高防守，多頭朝5萬點大關邁進。&#10;美國公布9月非農就業報告顯著降溫，市場對聯準會再度升息的預期緩和。&#10;本周鴻海、台積電營收與大立光法說登場，可望成為推升台股續強的催化劑。 |
| 31 | 中性 | 低 | Fed, ECB minutes in focus as weak US jobs data, French market stress c | In the US, solid economic growth has been bolstering the job market, allowing the Fed to zero in on inflation Read more  |
| 32 | 中性 | 中 | Africa's richest man Dangote's IPO out of reach in Nigeria | Dangote seeks $1.6 billion from investors to finance a $14.3 billion expansion and thus double the oil refinery's capaci |
| 33 | 正面 | 高 | 科技巨頭衝太空 AI 昇達科、仁寶、元晶、聯合再生等受惠 | 輝達執行長黃仁勳、SpaceX執行長馬斯克力挺太空資料中心趨勢，近期Google更透過SpaceX將旗下TPU伺服器送進太空軌道進行測試。科技巨頭們陸續邁入對太空資料中心實質測試階段，點亮太空AI新商機，助益昇達科、仁寶、元晶、聯合再生、華 |
| 34 | 中性 | 中 | UK events firm that hosts arms fairs and comic shows sold to rival for | FTSE 100 firm Informa to buy Clarion from private equity group Blackstone Business live – latest updates A British event |
| 35 | 負面 | 高 | 法國五大警訊升溫，法德利差飆至歐債危機高點、CDS創2013年來新高 | 【財訊快報／陳孟朔】路透報導，法國高負債與政治僵局疑慮持續升溫，市場壓力已由公債擴散至股票、銀行、信用風險與歐元。法國政府正尋求在2027年預算削減540億歐元支出，但隨明年總統大選逼近、國內抗議升溫，投資人對財政整頓能否順利推進愈發存疑， |
| 36 | 正面 | 高 | 鴻海德州廠動起來 供貨甲骨文 | 鴻海德州廠生產AI伺服器，全力支援甲骨文雲端基礎建設出貨。甲骨文雲端基礎建設（OCI）負責人暨執行副總裁Mahesh Thiagarajan近期也親訪鴻海德州廠，見證Vera Rubin平台AI機櫃產出。 |
| 37 | 正面 | 高 | 太空 AI 散熱議題成顯學 建準、奇鋐、雙鴻搶商機 | 輝達執行長黃仁勳今年初於財報會議中指出「太空AI需要更多散熱零組件，用量將比當前更大」，Google日前射TPU伺服器上太空，也將散熱視為後續優先觀察重點。法人看好，散熱是太空AI的新顯學，建準、奇鋐、雙鴻等台廠有望搭上商機。 |
| 38 | 負面 | 中 | The US is looking more like Italy | America is not so exceptional any more — and the New World is becoming more like the Old |
| 39 | 負面 | 高 | Average five-year fixed mortgage rate hits 6% for first time in three  | Banks and building societies raise prices as turmoil in bond markets increases expectations of base rate rise |
| 40 | 中性 | 中 | Sainsbury’s and Morrisons ‘held talks this year’ on multibillion-pound | Deal would have created a supermarket with a market share of 23.6%, still well behind Tesco’s 27.8% |
| 41 | 負面 | 中 | UK risks being 'uninvestable' if new oil and gas fields not approved,  | The boss of the Norwegian state company says further investment in the UK could be at risk if Rosebank and Jackdaw are n |
| 42 | 中性 | 中 | A new analyst call on Home Depot reflects our feeling on what to do wi | We're holding a small position in Home Depot to be ready for when rates eventually fall. |
| 43 | 正面 | 高 | Costa’s coffee shops return to profit with iced drinks and matcha on t | Costa Ltd reports operating profit of £20m in year to 31 December 2025 after losses of £13.5m in 2024 |
| 44 | 正面 | 高 | 美股強彈有利週一台股表現，留意權值電子股是否表態 | 【財訊快報／魏聖峰】美國上週五公布九月非農業就業報告降溫，暗示聯準會可能升息的預測降溫，激勵Nasdaq指數盤中創新高，收盤時Nasdaq指數上漲1.19%、費城半導體指數上漲2.4%，S&P 500指數上漲0.73%，道瓊工業指數上漲0. |
| 45 | 正面 | 高 | South Korean stock market value tops $4.1 trillion, nearly tripling in | South Korea&rsquo;s stock market crossed a milestone Monday, with the combined value of its two main bourses topping 6,0 |
| 46 | 負面 | 中 | G7釋儲震撼油市，紐油上週五一度急瀉逾5%、終場收跌1.90%，週線收黑 | 【財訊快報／陳孟朔】七國集團(G7)宣布聯手釋放1億桶柴油與原油緊急儲備，上週五瞬間引爆油市賣壓，紐約期油盤中一度急瀉逾5%，跌破每桶89美元，最低下探約88.06美元，布蘭特期油也一度重挫近4%。不過，隨市場重新評估中東戰事、柴油短缺與荷 |
| 47 | 正面 | 高 | 台股收盤新高！飆漲1236點至49712點 台積電新天價、老AI狂瀉 | 台股今（5日）展現超狂多頭氣勢，早盤即跳漲超過千點衝破49K大關，盤中最高觸及49770.66點，改寫歷史新頁，終場狂飆1236.30點收在49712.04點，成交量達1.1兆。台積電同步創下新高2580元，終場上漲75元收在2575元；台 |
| 48 | 正面 | 中 | How Malaysia offers Chinese investors Singapore’s comfort at prices lo | The lifestyle destination combines Singapore’s stability with Thailand’s prices and international schools cheaper than H |
| 49 | 正面 | 高 | 焦點股：南亞電子材料占比逼近六成，股價沿短均線創新高 | 【財訊快報／研究員周佳蓉】南亞(1303)今年上半年電子材料營收占比已由2025年的46.4%升至52.7%，8月再提高至59.8%，顯示正從傳統石化廠轉型為AI伺服器電子材料平台，除了持有南電(8046)61.4%、南亞科(2408)逾二 |
| 50 | 負面 | 中 | More Hong Kong homes sell at a loss despite signs prices have bottomed | There were at least 100 loss-making transactions for secondary homes in September despite prices edging higher, agents s |
| 51 | 正面 | 中 | Private Equity Firms Double Down on Fossil Fuels | Major private equity firms continue to hold extensive fossil fuel assets as rising energy demand, including from AI and  |
| 52 | 正面 | 低 | World’s biggest business class coming to British Airways’ A380s amid u | Changes to cut jets’ seating capacity, with bulk of reductions at the economy class cabins’ expense |
| 53 | 正面 | 中 | Freeport LNG Ramps Up Gas Intake After Train 2 Shutdown | Freeport LNG was ramping natural gas intake back toward normal levels on Monday after maintenance shut one of its three  |
| 54 | 中性 | 中 | Trump allows cheaper, dyed diesel on highways to blunt historic fuel c | The U.S. national average price of diesel topped $6 a gallon in September for the first time ever, as fuel supply disrup |
| 55 | 中性 | 高 | US supreme court hears big oil’s bid to block climate damage lawsuits | How the court will lean is unclear amid Suncor Energy and ExxonMobil’s attempt to stop lawsuits at state level |
| 56 | 正面 | 中 | Qualcomm to pay Huawei for first time in 5G, AI patent breakthrough | Mobile chipmakers' licensing deal will need U.S. regulatory approval |
| 57 | 正面 | 高 | Kia ranks 2nd in Jan.-Aug. auto sales in Britain on strong demand for  | Kia Motors Corp.'s sales in Britain ranked second in the January-August period, helped by strong demand for its Sportage |
| 58 | 負面 | 中 | 穀物週線上週齊挫，玉米大跌5.87%、豆粕急瀉6.47%，糖價逆勢飆漲 | 【財訊快報／陳孟朔】美國農產品期貨最近一週走勢明顯分化，穀物市場普遍承壓，其中玉米、豆粕跌勢最重，糖價則逆勢飆漲。上週五(2日)紐約穀物分類指數下跌0.48%，報32.9219點，週線累跌4.01%。芝加哥期貨交易所(CBOT)玉米期貨週線 |
| 59 | 負面 | 中 | Roadblocks in Pakistan capital to deter Imran Khan supporters | Opposition rallies in Islamabad on Sunday threaten further economic disruption |
| 60 | 正面 | 高 | 〈熱門股〉環宇-KY加速200G PD出貨 周漲15.21%站回500元大關 | 200G PD已導入量產，環宇-KY下半年隨InP基板供貨增加擴大出貨&#10;受惠1.6T應用拉動，AOC需求強勁，70mW CW Laser完成多家客戶驗證&#10;上周外資由賣轉買、投信連5買，股價周漲15.21%重返500元 |
| 61 | 正面 | 高 | Once in decline, Japan's hard-drive suppliers ride soaring AI demand | Coordination among companies has made country a leader in media, magnetic heads |
| 62 | 正面 | 中 | Ageing in Asia: Huge potential for the consumer economy | Healthcare, travel and tourism are the top 2 spending sectors for those aged 60 and above by 2030 Read more at The Busin |
| 63 | 正面 | 中 | Top Wall Street analysts are upbeat about the prospects for these 3 st | Investors with a long-term horizon can track ratings from top Wall Street analysts to find stocks with solid growth pros |
| 64 | 負面 | 中 | Investors look to shelter portfolios from rising AI concentration risk | Fund managers see hedge funds and emerging markets assets as bulwarks against sudden shift in sentiment on artificial in |
| 65 | 中性 | 中 | Britain’s Budget needs to tame spending and boost growth | Chancellor Healey can still make a low-key fiscal event a constructive one |
| 66 | 正面 | 高 | 台北紡織展經部秀研發成果　6亮點技術估帶動逾13億產值 | 2026台北紡織展（TITAS）今天登場，經濟部表示，技術司專館展出超過40項科專研發成果，其中6項亮點技術已導入業者產品開發，技轉金額合計約新台幣3400萬元，預估帶動逾13億元產值，其中紡織綜合所開發的「循環運動鞋」更獲2026年R&D |
| 67 | 正面 | 中 | Millennial Potash targets 2029 production as US-backed Gabon project a | "I don't want to replace Canadian potash," CEO said. "Actually, I want to replace Russian potash." |
| 68 | 負面 | 中 | UK car industry faces ‘difficult trade-off’ between Chinese and EU mar | Britain under pressure to put tariffs on cheap Chinese vehicle imports ahead of protectionist trade measures |
| 69 | 正面 | 中 | Schneider Electric nears deal to buy software group PTC for $20bn | Takeover is French conglomerate’s largest and enhances its products focused on manufacturers |
| 70 | 中性 | 中 | New BOK chief maps out cautious policy stance, wider financial stabili | South Korea&rsquo;s new central bank governor, Shin Hyun-song, struck a cautious tone on monetary policy Tuesday as risi |
| 71 | 中性 | 中 | 日銀審議委員佐藤綾野贊同逐步調整利率，密切關注消費和收入 | 【財訊快報／劉敏夫】外電報導指出，日本央行審議委員佐藤綾野(Ayano Sato)接受共同社採訪時表示，她贊同逐步調整利率的政策，但希望密切關注消費和收入的變化。佐藤綾野表示，個人消費的態勢並不強勁。同時，佐藤綾野還表示，她不認為升息應遵循 |
| 72 | 負面 | 高 | Why the era of cheap government debt is over | US debt has topped $40 trillion. How risky is the country's growing debt burden. And will investors keep funding Washing |
| 73 | 正面 | 中 | AI trade isn’t just about tech stocks but also power, TCW says | The artificial intelligence boom has sent investors racing into chipmakers, cloud providers and megacap technology stock |
| 74 | 負面 | 高 | Australia gas producers fume over domestic supply mandate | Companies argue loss of export revenue will slow investment in production |
| 75 | 負面 | 中 | The 'death' of back-office jobs: office work in the AI storm | From insurance payouts to banking, AI is taking over tasks that once took hours or days of human work – which office job |
| 76 | 負面 | 高 | Thai protesters slam Chinese, other foreign companies as economy slows | Government crackdown on ownership loophole could widen |
| 77 | 正面 | 低 | It's time for us to put cash to work in this ugly market. Here's where | In his Sunday column, Jim Cramer explains why investors need to hold their nose and do some buying. |
| 78 | 負面 | 高 | South-east Asia among economies most vulnerable to AI correction, Asea | The region is ‘particularly exposed’ as it is at the centre of global supply chains, it adds Read more at The Business T |
| 79 | 負面 | 高 | ‘Scarily thin’ global oil stocks could take two years to rebuild, Saud | A billion barrels of oil has been released from stocks so far Read more at The Business Times. |
| 80 | 正面 | 高 | Asian fixed income draws support from capex boom, shrinking dollar sup | Asia's fixed-income markets are entering the second half of 2026 with an unusually constructive combination of features: |
| 81 | 正面 | 中 | 歐洲天然氣價格週線走強，荷蘭TTF大漲7.72%、英國天然氣期貨升4.68% | 【財訊快報／陳孟朔】歐洲天然氣價格上週五(2日)續升，市場持續消化能源供應風險與冬季庫存前景，帶動荷蘭與英國基準天然氣期貨同步走高，其中荷蘭TTF天然氣週線漲幅超過7%，成為歐洲能源市場近期相對強勢的品種。作為歐洲基準的荷蘭TTF天然氣期貨 |
| 82 | 正面 | 中 | 川普政府擬放寬免稅柴油使用限制，降低燃料成本 | 【財訊快報／劉敏夫】外電報導指出，美國川普政府據稱計畫放寬免稅柴油使用限制，藉此降低燃料成本。美國總統川普準備放寬對一種免稅柴油的使用限制，這是他在11月中期選舉前降低這種重要燃料成本的最新舉措。以討論未公開消息為由要求匿名的知情人士透露， |
| 83 | 負面 | 高 | Turkey: Stock market scandal hits half a million investors | Asset managers are alleged to have artificially inflated the value of their funds. Turkish authorities have made multipl |
| 84 | 中性 | 中 | 台電：現階段無電價調整規劃　盼國會支持追加預算 | 有媒體報導，台電研議對5MW以上用電大戶收「加成折舊費」的差別電價，對象鎖定半導體等產業。台電今天表示，行政院日前拍板115年度追加預算案，已編列新台幣711億元預算撥補台電，照顧民生，免受燃料價格飆漲直接衝擊，並強調現階段無任何電價調整規 |
| 85 | 中性 | 中 | Japan's TEPCO to counter 'capacity squatters' in AI data center boom | Tokyo power company's new rules aim to prevent stranded capacity |
| 86 | 正面 | 高 | 星艦引爆太空運算革命！次世代「AI運算衛星」超級循環啟動 | 星艦運載技術突破，發射成本自數千美元降至200美元以下，推動低軌衛星升級。&#10;Starlink V3由通訊節點轉為AI運算衛星，並帶動直連手機與星間光學傳輸需求。&#10;台系供應鏈受惠，昇達科、華通、穩懋、台光電等切入射頻、PCB與 |
| 87 | 正面 | 高 | Kayne Anderson expects capital inflows to US alternative real estate s | Kayne Anderson Real Estate, the real estate investment arm of Kayne Anderson, expects significant capital rotation into  |
| 88 | 負面 | 中 | 韓國未敲定阿拉斯加LNG投資，川普揚言收費加倍 | 【財訊快報／陳孟朔】美國總統川普上週五(2日)表示，如果韓國不盡快簽署投資阿拉斯加液化天然氣(LNG)項目的協議，美方將提高對韓方的「收費標準」，甚至可能加倍。路透報導，川普最近一週宣布，韓國將對美國能源與基礎建設項目投資2,000億美元， |
| 89 | 正面 | 高 | 面板雙虎轉型　法人聚焦先進封裝技術進展 | 面板雙虎轉型跨入半導體先進封裝領域的進度受市場矚目，低價轉機題材成為推升股價的最大動能，群創及友達分別創下股價高點。法人表示，股價反映轉型題材，將持續追蹤先進封裝發展進度。 |
| 90 | 負面 | 中 | South-east Asia’s LNG hunger sparks caution over volatile prices, infr | Observers call for faster shift away from ‘roller coaster’ fuel after major supply disruptions Read more at The Business |
| 91 | 正面 | 中 | Asset-heavy, cash-flow-backed investments gain appeal in lower-return  | Investors should shift toward asset-heavy investments backed by contractual cash flow as years of strong gains in global |
| 92 | 負面 | 中 | 俄羅斯擬大砍煉油補貼，2027年急降39%、2029年縮至8120億盧布 | 【財訊快報／陳孟朔】俄羅斯政府計畫大幅削減對國內煉油廠的燃料補貼，顯示在財政壓力升高之際，莫斯科正逐步降低維持國內成品油供應的政策支出。外電引述根據提交國家杜馬(國會)的2027至2029年預算草案與相關文件顯示，俄羅斯2027年向煉油廠提 |
| 93 | 中性 | 中 | Data centre operator Firmus said to plan allocating half of IPO to exi | This positions Nvidia and Blackstone to increase their stakes Read more at The Business Times. |
| 94 | 正面 | 高 | Reactor refurbishments to drive near-term nuclear growth: Candu Energy | Refurbishment of aging nuclear reactors is expected to drive growth in the industry over the next five to 10 years as mo |
| 95 | 正面 | 中 | Floating Power Plants Are Opening a New Energy Frontier | Floating solar, nuclear and wave-energy technologies could expand low-carbon electricity generation while reducing press |
| 96 | 正面 | 中 | IC 設計釀新一波漲價潮 客戶未雨綢繆...積極拉貨 | 晶圓代工廠持續評估調高報價，IC設計業者可能在今年底跟進啟動今年第二次漲價。IC設計業者指出，今年以來下游客戶開始出現一些拉貨動能，原因來自擔憂中東戰事、AI持續排擠產能等因素，擔心未來成本繼續走高，為鎖住利潤空間才出現拉貨。 |
| 97 | 中性 | 低 | US lead in AI over China narrows after DeepSeek gains: report | That improving performance spells further market share gains for Chinese contenders Read more at The Business Times. |
| 98 | 負面 | 中 | How India became dangerously addicted to Chinese imports | Indiaâs toy shops provide an unlikely barometer by which to measure its economic relationship with China. |
| 99 | 正面 | 高 | Musk is a trillionaire again as SpaceX claws back post-IPO slump | It marks the first time in three months the 55-year-old tech mogul’s fortune passed US$1 trillion |
| 100 | 負面 | 高 | Honda delays next-gen CR-V hybrid production several months in US, Can | Overhauled SUV model's mass production pushed back to at least April 2027 |
| 101 | 正面 | 中 | Iraq shifts oil strategy by arranging tanker to move past Hormuz | This may help the country reach refiners reluctant to send vessels through the strait Read more at The Business Times. |
| 102 | 負面 | 低 | UK reviewing whether to impose tariffs on Chinese car imports to align | Move would strengthen Britain’s case to be included in new legislation to protect European manufacturing |
| 103 | 正面 | 中 | Partners Group eyes special opportunities, royalties to outplay market | Partners Group is positioning itself to benefit from market disruptions stemming from Middle East conflicts, liquidity p |
| 104 | 正面 | 中 | 哈塞特稱非農符合預期，指荷姆茲恢復通行、白宮聚焦降赤字 | 【財訊快報／陳孟朔】外電報導，白宮國家經濟委員會主任哈塞特(Kevin Hassett)上週五(2日)表示，美國9月非農就業報告雖僅新增2.9萬人，但整體結果「符合預期」，他對數據並不失望，並稱政府部門就業減少之際，其他產業就業仍有增長。哈 |
| 105 | 負面 | 高 | Iran says Hormuz strait will not reopen until conditions are met: repo | This comes a few days after Teheran received Washington’s reply to its diplomatic proposal Read more at The Business Tim |
| 106 | 負面 | 高 | 美國市政債券指數9月重挫4.4%，創雷曼危機以來最差單月表現 | 【財訊快報／陳孟朔】美國市政債券9月遭遇全球金融危機以來最猛烈拋售，通膨疑慮、聯準會(Fed)進一步升息風險及美債殖利率急升同步施壓。彭博市政債券指數9月下跌約4.4%，創2008年9月雷曼兄弟倒閉以來最差單月表現，長天期債券因久期較高、對 |
| 107 | 中性 | 中 | Gulf Producers Say Importers Should Share the Cost of Hormuz Workaroun | Saudi Aramco’s Amin Nasser and Kuwait’s KPC chief want outside investment in Hormuz bypass routes and fuel storage close |
| 108 | 正面 | 高 | Greenland Mines authorizes $20M share buyback | The company can repurchase up to $20 million of its outstanding common stock from time to time through open-market trans |
| 109 | 中性 | 中 | 台塑石化：5日起汽柴油不漲價 | 雖然國際油價維持高檔，但中油宣布凍漲汽柴油價格，台塑石化今天網站資料也顯示維持不漲價；此為自9月13日宣布9月14日調漲汽油價格後，已連續3週未調整油價。 |
| 110 | 負面 | 中 | Will Germany have enough gas this winter amid energy supply crunch? | Germany's gas storage sites are far less full than in recent years. Officials say supplies are secure, but analysts warn |
| 111 | 中性 | 中 | Why ordinary investors struggle to buy into the robotics boom | Most of the companies building the robots of the future are still private, leaving ordinary investors with limited optio |
| 112 | 負面 | 高 | G7釋儲重擊柴油，歐洲低硫柴油期貨上週五收挫4.24%、週線急瀉8.45% | 【財訊快報／陳孟朔】全球柴油市場上週五(2日)遭遇猛烈拋售，七國集團(G7)同意透過國際能源署(IEA)協調釋放1億桶柴油與原油緊急儲備，並在前20天優先大規模投放柴油，直接打擊近期漲勢最凌厲的成品油。歐洲柴油期貨盤中一度重挫5.75%，顯 |
| 113 | 中性 | 高 | 克里夫蘭聯儲總裁估，Fed月底會議前仍有時間評估下一步政策 | 【財訊快報／陳孟朔】路透報導，克里夫蘭聯邦銀行總裁哈瑪克(Beth Hammack)上週五(2日)表示，美國9月就業報告與近期就業趨勢大致一致，而距離10月底聯邦公開市場委員會(FOMC)會議仍有一段時間，因此Fed仍可等待更多數據，再決定 |
| 114 | 負面 | 高 | Strikes by North Sea oil workers could ‘severely disrupt’ UK fuel supp | Union says staff left with no choice but industrial action after breakdown in pay talks with Texas oil firm Apache |
| 115 | 負面 | 高 | Dealmaking slowdown threatens early end to M&A boom | Interest rate rises, AI anxiety and midterm elections cool animal spirits after record-breaking start to the year |
| 116 | 負面 | 中 | Quality over quantity: China’s AI microdrama producers battle viewer f | Challenge has shifted from making videos at low cost to standing out in a market saturated with lookalike productions, c |
| 117 | 正面 | 高 | Saudi Arabia and UAE to bolster Asia's oil reserves | 2 nations seen expanding exports and offering priority supplies in emergencies |
| 118 | 負面 | 高 | Swanson results fall short despite 6.05-g/t gold highlight | Although some of its holes returned encouraging grades, the results did not demonstrate strong continuity. |
| 119 | 負面 | 中 | The top 50 biggest mining companies in the world | Gold stocks falter, copper miners ignore a record price and only one lithium producer survives in the second-worst month |
| 120 | 正面 | 高 | H&R Block: A Boring Business With An Interesting Return | H&R Block buy case: 7x cash flow, AI-driven growth beyond tax season, focus on complex & SMB clients, and strong buyback |
| 121 | 負面 | 高 | 越南油價3個月飆2成通膨有感  台商嘆人工與運輸成本皆漲 | 越南燃油價格近3個月累積漲幅超過2成，推高生產、運輸和商品成本，加劇通膨壓力，今年前8個月的平均消費者物價也比去年同期上漲逾4%。台商告訴中央社，光人工成本就調漲逾1成，運輸費與報價頻率也大增。 |
| 122 | 正面 | 高 | 大盤登頂誰最賺？18檔ETF同創新高 主動式、市值型、海外科技全上榜 | 台股10/2收48,475.74點創新高，上市櫃市值達170.17兆元&#10;18檔ETF同步創高，主動式ETF占8檔，涵蓋台股、全球科技、資安與ESG |
| 123 | 正面 | 高 | Meta Muse popularity lifts AMD stock to fresh highs as AI agents juice | The personal agent boom is lifting the fortunes of AMD and Intel, which have outperformed their megacap tech peers over  |
| 124 | 正面 | 高 | Vietnam’s northern provinces, not Hanoi or Ho Chi Minh City, are power | The country’s economic acceleration is showing up far beyond its two biggest cities |
| 125 | 正面 | 中 | Taiwan's AUO, Innolux bet on glass as next-gen AI chip material | Warp resistance of novel substrate means bigger, more powerful circuit boards |
| 126 | 中性 | 中 | Asian gold producers begin hoarding domestic supplies after price rise | Eroding confidence in the dollar and concerns over sanctions fuel 'resource nationalism' |
| 127 | 正面 | 高 | 法人看好10月有這些利多 台股預估成交量飆至1.3兆元叩關5萬點 | 台指期突破50000點，激勵台股今盤中大漲逾1200點，預估成交量逾1.3兆元。&#10;台積電盤中貢獻556點，台達電、聯發科、台光電、日月光投控等權值股同步推升指數。&#10;留意美債殖利率偏高與急漲後短線震盪。 |
| 128 | 負面 | 中 | Nvidia's $20 billion Groq deal faces lawsuit alleging startup's stockh | The case alleges that the licensing deal "squeezed out" stockholders by giving them a "lowball price." |
| 129 | 正面 | 高 | Discovery silver project clears key Mexico hurdle | Mexico’s environmental department approval completed the project’s federal environmental approval process. |
| 130 | 正面 | 中 | 烏克蘭實戰無人機公司AEVEX將在台量產、採台廠零件！美大廠聯手中光電子公司，靠3D列印造無人機 | 鳳凰幽靈（Phoenix Ghost）自殺無人機在烏克蘭戰爭中一戰成名，其製造商AEVEX Aerospace首度來台舉行記者會。這家今年4月才在紐約證交所掛牌上市的國防科技公司，正式宣布與台灣的中光電智能機器人（CiRC）建立策略聯盟。雙 |
| 131 | 中性 | 中 | BT agrees rescue deal to buy broadband operator TalkTalk | The takeover still needs to be approved by the regulator, but would give certainty to TalkTalk's millions of customers |
| 132 | 中性 | 中 | Fuel Price Shock Pushes Global Gas Car Sales Below 50% for First Time | The share of gasoline cars in global vehicle sales fell below 50% for the first time ever as the Hormuz shock and the re |
| 133 | 負面 | 高 | Average five-year mortgage rate hits 6% for first time in three years | The cost of a new fixed-rate mortgage has been rising in recent weeks as lenders face higher costs. |
| 134 | 正面 | 高 | 信驊營收好威 連11月締新猷 遠端伺服器控制晶片需求強勁帶旺後市 | 股王信驊昨（5）日公布9月合併營收16.36億元，連續11個月創單月歷史新高，推升第3季業績改寫單季新猷並優於預期。法人指出，AI市況持續火熱，推升BMC（遠端伺服器控制晶片）需求強勁，信驊為BMC龍頭，將持續大咬AI商機，帶旺營運。 |
| 135 | 中性 | 中 | China's economic reset starts at city hall | Beijing is replacing land-driven growth with revenue tied to consumption |
| 136 | 負面 | 高 | Europe’s Diesel Woes Just Got Even Worse | Europe’s diesel supply crunch is worsening, with imports hitting a record September low as China suspends fuel exports a |
| 137 | 中性 | 中 | Paramount and Warner Bros complete merger to form Hollywood giant Skyd | Two of America’s oldest film studios have completed their merger, bringing CNN, HBO and franchises including The Godfath |
| 138 | 正面 | 中 | Is Germany's economic slump finally over? | Despite a slew of negative headlines, the German economy has posted its best figures in years. There are reasons for opt |
| 139 | 負面 | 中 | 川普欲售委內瑞拉黃金 美國自設法規反噬交易 | 圖／本報資料庫商傳媒｜吳承岳／台北報導儘管美國總統川普曾公開展示委內瑞拉的黃金條塊，並表示美國政府有意將這些黃金變現，然而，數億美元的委內瑞拉黃金至今仍存放在美國的倉庫中，未被加工銷售。這項計畫面臨挑戰，部分原因竟是美國自身制定的嚴格法規所 |
| 140 | 正面 | 高 | 5 Natural Gas Stocks Profiting From the Strait of Hormuz Standoff | When Iran struck Qatar's Ras Laffan complex in March and knocked out 17% of the country's LNG export capacity, the trade |
| 141 | 中性 | 中 | 韓國9月核心通膨仍達2.8%、出口創新高，BOK 11月再升息預期升溫 | 【財訊快報／陳孟朔】韓國9月整體通膨雖降至3%以下，但核心物價壓力仍具黏性，加上半導體出口爆發、單月出口刷新歷史紀錄，使市場對韓國央行(BOK)11月恢復升息的預期升溫。分析人士認為，強勁出口降低進一步緊縮對經濟成長的衝擊，讓央行在壓制通膨 |
| 142 | 負面 | 高 | Germany faces energy tax losses as EV sales rise | The rapid shift to electric vehicles in Germany is cutting fuel tax revenue for the government. As EV sales surge, polic |
| 143 | 負面 | 高 | 美舉債成本居20年高點　政府3力道應對恐難逃刺激通膨 | 美國政府舉債成本不斷攀高，如今40兆餘美元債務每年須付息達約1兆美元。為控制情勢，從財政部到聯邦準備理事會（Fed）有若干選項，但越是激烈越可能釀成通貨膨脹惡化。 |
| 144 | 正面 | 高 | 金融圈傳奇女將江威娜掌舵 盛大資訊興櫃首日衝百元 | 資服廠盛大資訊（7950）9月30日以每股27元登錄興櫃，掛牌交易首日股價最高價一度衝上108.5元，飆漲301.85%，股價翻逾4倍，漲幅更成為今年9月登錄興櫃公司之冠，終場以103元作收，漲幅亦高達281.4%，為近期掛牌最大黑馬，啟動 |
| 145 | 正面 | 中 | Oil Prices Fall as Hormuz Crude Flows Top Pre-War Levels | Kpler data shows oil flows through the Strait of Hormuz topped pre-war levels in late September, but Brent still trades  |
| 146 | 中性 | 中 | Kawasaki Heavy aims for fully autonomous humanoid AI robot by 2030 | Kaleido android to incorporate homegrown platform under development by Noetra |
| 147 | 中性 | 高 | Baltic Exchange Shipping Insights | A roundup of the week’s tanker and dry bulk market (Aug 7, 2026) Read more at The Business Times. |
| 148 | 正面 | 中 | European structured credit beckons Korean investors with potential for | Nearly two decades after the global financial crisis saddled structured finance with a reputation for opacity and risk,  |
| 149 | 正面 | 中 | 00830近一年翻倍？國泰費城半導體ETF成分股、配息與定期定額一次看 | AI資本支出續強，雲端服務商擴大AI基礎建設投資，帶動晶片、伺服器與半導體設備需求升溫。&#10;00830追蹤費城半導體指數，成分股涵蓋輝達、博通、美光、台積電ADR、艾司摩爾等半導體龍頭。&#10;半導體長線成長明確但波動大，定期定額搭 |
| 150 | 負面 | 高 | Chungho Nais sale faces fresh questions amid Carlyle talks | The planned sale of Chungho Nais Co. is facing fresh uncertainty after the South Korean water purifier maker reported a  |