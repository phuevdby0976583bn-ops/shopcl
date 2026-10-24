from enums.language import Language

def get_wallet_text(language: Language, user_name: str, telegram_id: int, balance: float, top_up: float, consume: float) -> tuple[str, dict]:
    match language:
        case Language.VI:
            text = (
                "?? <b>V? & T?I KHO?N C?A B?N</b>\n"
                "??????????????????????\n"
                f"?? <b>T?i kho?n:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"?? <b>S? d? kh? d?ng:</b> <b>{balance}$</b> (USDT)\n"
                f"?? <b>?? n?p:</b> {top_up:.2f}$ | ?? <b>?? ti?u:</b> {consume:.2f}$\n"
                "??????????????????????\n"
                "? <i>Khuy?n d?ng <b>Binance Pay</b> ho?c <b>VietQR BIDV</b>: N?p t? ??ng nh?n ngay sau v?i gi?y.</i>\n"
                "?? <b>B?m n?t b?n d??i ?? n?p ti?n t? ??ng:</b>"
            )
            buttons = {
                "bank": "?? Chuy?n kho?n Ng?n h?ng (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Ph? - Nh?n 1s)",
                "onchain": "?? N?p On-chain (BSC, TRX, TON...)",
                "history": "?? L?ch s? mua h?ng"
            }
        case Language.ZH:
            text = (
                "?? <b>???????</b>\n"
                "??????????????????????\n"
                f"?? <b>??:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"?? <b>????:</b> <b>${balance}</b> (USDT)\n"
                f"?? <b>????:</b> ${top_up:.2f} | ?? <b>????:</b> ${consume:.2f}\n"
                "??????????????????????\n"
                "? <i>???? <b>???? (Binance Pay)</b>?0????1-5????????</i>\n"
                "?? <b>??????????????</b>"
            )
            buttons = {
                "bank": "?? ?????? (VietQR / BIDV)",
                "binance": "?? ???? Binance Pay (0??? - ??)",
                "onchain": "?? ???? (BSC, TRX, TON...)",
                "history": "?? ??????"
            }
        case Language.HI:
            text = (
                "?? <b>???? ????? ?? ????</b>\n"
                "??????????????????????\n"
                f"?? <b>????:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"?? <b>?????? ???:</b> <b>${balance}</b> (USDT)\n"
                f"?? <b>???:</b> ${top_up:.2f} | ?? <b>????:</b> ${consume:.2f}\n"
                "??????????????????????\n"
                "? <i>????????: <b>Binance Pay</b> (0% ?????, 1-5 ????? ??? ???????? ???)?</i>\n"
                "?? <b>??? ???? ?? ??? ???? ??? ?? ??? ?? ????? ????:</b>"
            )
            buttons = {
                "bank": "?? ??????? ???? ???????? (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% ????? - ????? 1s)",
                "onchain": "?? ??-??? ???????? (BSC, TRX, TON...)",
                "history": "?? ??????? ?? ??????"
            }
        case Language.FR:
            text = (
                "?? <b>VOTRE PORTEFEUILLE & COMPTE</b>\n"
                "??????????????????????\n"
                f"?? <b>Compte:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"?? <b>Solde disponible:</b> <b>{balance}$</b> (USDT)\n"
                f"?? <b>D?pos?:</b> {top_up:.2f}$ | ?? <b>D?pens?:</b> {consume:.2f}$\n"
                "??????????????????????\n"
                "? <i>Recommand?: <b>Binance Pay</b> (0% frais, cr?dit instantan? en 1-5s).</i>\n"
                "?? <b>Appuyez sur un bouton ci-dessous pour d?poser:</b>"
            )
            buttons = {
                "bank": "?? Virement Bancaire Vietnam (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Frais - Instant 1s)",
                "onchain": "?? D?p?t On-chain (BSC, TRX, TON...)",
                "history": "?? Historique des Achats"
            }
        case Language.DE:
            text = (
                "?? <b>IHRE GELDB?RSE & KONTO</b>\n"
                "??????????????????????\n"
                f"?? <b>Konto:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"?? <b>Verf?gbares Guthaben:</b> <b>{balance}$</b> (USDT)\n"
                f"?? <b>Eingezahlt:</b> {top_up:.2f}$ | ?? <b>Ausgegeben:</b> {consume:.2f}$\n"
                "??????????????????????\n"
                "? <i>Empfohlen: <b>Binance Pay</b> (0% Geb?hr, Gutschrift in 1-5s).</i>\n"
                "?? <b>W?hlen Sie unten eine Einzahlungsmethode:</b>"
            )
            buttons = {
                "bank": "?? Vietnam Bank?berweisung (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Geb?hr - Sofort 1s)",
                "onchain": "?? On-chain Einzahlung (BSC, TRX, TON...)",
                "history": "?? Kaufhistorie"
            }
        case Language.IT:
            text = (
                "?? <b>IL TUO PORTAFOGLIO & ACCOUNT</b>\n"
                "??????????????????????\n"
                f"?? <b>Account:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"?? <b>Saldo disponibile:</b> <b>{balance}$</b> (USDT)\n"
                f"?? <b>Depositato:</b> {top_up:.2f}$ | ?? <b>Speso:</b> {consume:.2f}$\n"
                "??????????????????????\n"
                "? <i>Consigliato: <b>Binance Pay</b> (0% commissioni, accredito istantaneo in 1-5s).</i>\n"
                "?? <b>Tocca un pulsante sotto per depositare:</b>"
            )
            buttons = {
                "bank": "?? Bonifico Bancario Vietnam (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Commissioni - Immediato 1s)",
                "onchain": "?? Deposito On-chain (BSC, TRX, TON...)",
                "history": "?? Storico Acquisti"
            }
        case Language.ES:
            text = (
                "?? <b>TU BILLETERA & CUENTA</b>\n"
                "??????????????????????\n"
                f"?? <b>Cuenta:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"?? <b>Saldo disponible:</b> <b>${balance}</b> (USDT)\n"
                f"?? <b>Depositado:</b> ${top_up:.2f} | ?? <b>Gastado:</b> ${consume:.2f}\n"
                "??????????????????????\n"
                "? <i>Recomendado: <b>Binance Pay</b> (0% comisi?n, acreditaci?n instant?nea en 1-5s).</i>\n"
                "?? <b>Toca un bot?n abajo para depositar:</b>"
            )
            buttons = {
                "bank": "?? Transferencia Bancaria Vietnam (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Comisi?n - Instant?neo 1s)",
                "onchain": "?? Dep?sito On-chain (BSC, TRX, TON...)",
                "history": "?? Historial de Compras"
            }
        case _:
            text = (
                "?? <b>YOUR WALLET & ACCOUNT</b>\n"
                "??????????????????????\n"
                f"?? <b>Account:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"?? <b>Available Balance:</b> <b>${balance}</b> (USDT)\n"
                f"?? <b>Deposited:</b> ${top_up:.2f} | ?? <b>Spent:</b> ${consume:.2f}\n"
                "??????????????????????\n"
                "? <i>Recommended: <b>Binance Pay</b> (0% fee, instant credit in 1-5s).</i>\n"
                "?? <b>Tap a button below to deposit:</b>"
            )
            buttons = {
                "bank": "?? Vietnam Bank Transfer (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Fee - Instant 1s)",
                "onchain": "?? Other Wallets / Exchanges (On-chain)",
                "history": "?? Purchase History"
            }
    return text, buttons


def get_deposit_method_selection(language: Language) -> tuple[str, dict]:
    match language:
        case Language.VI:
            text = (
                "?? <b>B?N MU?N N?P TI?N B?NG C?CH N?O?</b>\n"
                "??????????????????????\n"
                "?? <b>Ng?n H?ng Vi?t Nam:</b> Qu?t m? VietQR chuy?n kho?n BIDV, t? ??ng c?ng ti?n 10s.\n"
                "? <b>Binance Pay:</b> 0% ph? chuy?n, n?p t? ??ng nh?n ngay sau 1-5 gi?y.\n"
                "?? <b>On-chain:</b> N?p qua USDT c?c m?ng BSC, Solana, Tron, ERC20.\n"
                "??????????????????????\n"
                "?? <i>Vui l?ng ch?n h?nh th?c b?n d??i:</i>"
            )
            buttons = {
                "bank": "?? Chuy?n kho?n Ng?n h?ng (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% ph? - Nh?n ngay 1s)",
                "onchain": "?? V? / S?n kh?c (On-chain BSC, TRX, TON...)"
            }
        case Language.ZH:
            text = (
                "?? <b>?????????</b>\n"
                "??????????????????????\n"
                "?? <b>???? (VietQR):</b> BIDV ???????? 10-30 ???????\n"
                "? <b>???? (Binance Pay):</b> 0 ????1-5 ??????\n"
                "?? <b>???? (On-chain):</b> ?? BSC (BEP20), Tron (TRC20), TON ????\n"
                "??????????????????????\n"
                "?? <i>?????????????</i>"
            )
            buttons = {
                "bank": "?? ?????? (VietQR / BIDV)",
                "binance": "?? ???? Binance Pay (0??? - ??)",
                "onchain": "?? ?????? (On-chain BSC, TRX...)"
            }
        case Language.HI:
            text = (
                "?? <b>???? ??? ???? ?????</b>\n"
                "??????????????????????\n"
                "?? <b>??????? ????:</b> VietQR ???????? (BIDV), 10-30 ????? ??? ????? ????\n"
                "? <b>Binance Pay:</b> 0% ?????, 1-5 ????? ??? ?????? ????????\n"
                "?? <b>??-???:</b> BSC, Tron, TON ?? ?????? ?? USDT ??? ?????\n"
                "??????????????????????\n"
                "?? <i>????? ???? ??? ?? ???????? ??? ?? ?????:</i>"
            )
            buttons = {
                "bank": "?? ??????? ???? ???????? (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% ????? - ????? 1s)",
                "onchain": "?? ???? ????? / ???????? (On-chain)"
            }
        case Language.FR:
            text = (
                "?? <b>CHOISISSEZ VOTRE MODE DE D?P?T</b>\n"
                "??????????????????????\n"
                "?? <b>Banque Vietnam:</b> Virement VietQR instantan? (BIDV), auto en 10s.\n"
                "? <b>Binance Pay:</b> 0% frais, cr?dit instantan? en 1-5 secondes.\n"
                "?? <b>On-chain:</b> D?posez des USDT via BSC, Tron, TON, ERC20.\n"
                "??????????????????????\n"
                "?? <i>Veuillez s?lectionner une option ci-dessous:</i>"
            )
            buttons = {
                "bank": "?? Virement Bancaire Vietnam (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Frais - Instant 1s)",
                "onchain": "?? Autres Portefeuilles (On-chain)"
            }
        case Language.DE:
            text = (
                "?? <b>W?HLEN SIE IHRE EINZAHLUNGSMETHODE</b>\n"
                "??????????????????????\n"
                "?? <b>Vietnam Bank:</b> VietQR ?berweisung (BIDV), automatische Gutschrift in 10s.\n"
                "? <b>Binance Pay:</b> 0% Geb?hr, Sofortgutschrift in 1-5 Sekunden.\n"
                "?? <b>On-chain:</b> Zahlen Sie USDT ?ber BSC, Tron, TON, ERC20 ein.\n"
                "??????????????????????\n"
                "?? <i>Bitte w?hlen Sie eine Option:</i>"
            )
            buttons = {
                "bank": "?? Vietnam Bank?berweisung (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Geb?hr - Sofort 1s)",
                "onchain": "?? Andere Wallets / Exchanges (On-chain)"
            }
        case Language.IT:
            text = (
                "?? <b>SCEGLI IL TUO METODO DI DEPOSITO</b>\n"
                "??????????????????????\n"
                "?? <b>Banca Vietnam:</b> Bonifico istantaneo VietQR (BIDV), accredito in 10s.\n"
                "? <b>Binance Pay:</b> 0% commissioni, accredito immediato in 1-5 secondi.\n"
                "?? <b>On-chain:</b> Deposita USDT tramite reti BSC, Tron, TON, ERC20.\n"
                "??????????????????????\n"
                "?? <i>Seleziona un'opzione qui sotto:</i>"
            )
            buttons = {
                "bank": "?? Bonifico Bancario Vietnam (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Commissioni - Immediato 1s)",
                "onchain": "?? Altri Portafogli (On-chain)"
            }
        case Language.ES:
            text = (
                "?? <b>ELIGE TU M?TODO DE DEP?SITO</b>\n"
                "??????????????????????\n"
                "?? <b>Banco Vietnam:</b> Transferencia instant?nea VietQR (BIDV), auto en 10s.\n"
                "? <b>Binance Pay:</b> 0% comisi?n, acreditaci?n instant?nea en 1-5 segundos.\n"
                "?? <b>On-chain:</b> Deposita USDT mediante redes BSC, Tron, TON, ERC20.\n"
                "??????????????????????\n"
                "?? <i>Por favor selecciona una opci?n abajo:</i>"
            )
            buttons = {
                "bank": "?? Transferencia Bancaria Vietnam (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Comisi?n - Instant?neo 1s)",
                "onchain": "?? Otras Billeteras (On-chain)"
            }
        case _:
            text = (
                "?? <b>CHOOSE YOUR DEPOSIT METHOD</b>\n"
                "??????????????????????\n"
                "?? <b>Vietnam Bank:</b> VietQR instant transfer (BIDV), auto-credit in 10s.\n"
                "? <b>Binance Pay:</b> 0% fee, instant credit in 1-5 seconds.\n"
                "?? <b>On-chain:</b> Deposit USDT via BSC, Solana, Tron, ERC20.\n"
                "??????????????????????\n"
                "?? <i>Please choose an option below:</i>"
            )
            buttons = {
                "bank": "?? Vietnam Bank Transfer (VietQR / BIDV)",
                "binance": "?? Binance Pay (0% Fee - Instant 1s)",
                "onchain": "?? Other Wallets / Exchanges (On-chain)"
            }
    return text, buttons


def get_out_of_stock_text(language: Language, cat_name: str, subcat_name: str) -> str:
    match language:
        case Language.VI:
            return (
                f"?? <b>Danh m?c:</b> <code>{cat_name}</code>\n"
                f"?? <b>Lo?i t?i kho?n:</b> <code>{subcat_name}</code>\n\n"
                f"? <b>T?m th?i h?t h?ng!</b>\n"
                f"Kho hi?n t?i ?? b?n h?t lo?i t?i kho?n n?y. Vui l?ng ch?n lo?i t?i kho?n kh?c ho?c li?n h? Admin @truongdvfb ?? ???c h? tr? nh?p th?m h?ng."
            )
        case Language.ZH:
            return (
                f"?? <b>??:</b> <code>{cat_name}</code>\n"
                f"?? <b>????:</b> <code>{subcat_name}</code>\n\n"
                f"? <b>?????</b>\n"
                f"??????????????????????? @truongdvfb ???"
            )
        case Language.HI:
            return (
                f"?? <b>??????:</b> <code>{cat_name}</code>\n"
                f"?? <b>????:</b> <code>{subcat_name}</code>\n\n"
                f"? <b>??? ?? ?????!</b>\n"
                f"?? ?????? ??????? ??? ?????? ?? ??? ??? ????? ??? ???? ?????? ??????"
            )
        case Language.FR:
            return (
                f"?? <b>Cat?gorie:</b> <code>{cat_name}</code>\n"
                f"?? <b>Compte:</b> <code>{subcat_name}</code>\n\n"
                f"? <b>Rupture de stock!</b>\n"
                f"Ce type de compte est actuellement ?puis?. Veuillez choisir un autre produit."
            )
        case Language.DE:
            return (
                f"?? <b>Kategorie:</b> <code>{cat_name}</code>\n"
                f"?? <b>Konto:</b> <code>{subcat_name}</code>\n\n"
                f"? <b>Ausverkauft!</b>\n"
                f"Dieser Produkttyp ist derzeit vergriffen. Bitte w?hlen Sie ein anderes Produkt."
            )
        case Language.IT:
            return (
                f"?? <b>Categoria:</b> <code>{cat_name}</code>\n"
                f"?? <b>Account:</b> <code>{subcat_name}</code>\n\n"
                f"? <b>Esaurito!</b>\n"
                f"Questo tipo di account ? attualmente esaurito. Scegli un altro prodotto."
            )
        case Language.ES:
            return (
                f"?? <b>Categor?a:</b> <code>{cat_name}</code>\n"
                f"?? <b>Cuenta:</b> <code>{subcat_name}</code>\n\n"
                f"? <b>?Agotado!</b>\n"
                f"Este tipo de cuenta est? actualmente agotado. Por favor selecciona otro producto."
            )
        case _:
            return (
                f"?? <b>Category:</b> <code>{cat_name}</code>\n"
                f"?? <b>Account:</b> <code>{subcat_name}</code>\n\n"
                f"? <b>Out of stock!</b>\n"
                f"This account type is currently out of stock. Please select another product or contact Admin @truongdvfb."
            )


def get_select_quantity_text(language: Language, cat_name: str, subcat_name: str, unit_price: float, sym: str, desc: str, available_qty: int) -> str:
    match language:
        case Language.VI:
            return (
                f"?? <b>Danh m?c:</b> <code>{cat_name}</code>\n"
                f"?? <b>Lo?i t?i kho?n:</b> <code>{subcat_name}</code>\n"
                f"?? <b>Gi? b?n:</b> <code>{unit_price:.2f} {sym}</code> / nick\n"
                f"?? <b>M? t?:</b> <i>{desc}</i>\n"
                f"?? <b>S? l??ng c? s?n:</b> <code>{available_qty}</code> c?i\n\n"
                f"?? <b>Vui l?ng ch?n s? l??ng c?n mua:</b>"
            )
        case Language.ZH:
            return (
                f"?? <b>??:</b> <code>{cat_name}</code>\n"
                f"?? <b>????:</b> <code>{subcat_name}</code>\n"
                f"?? <b>??:</b> <code>{unit_price:.2f} {sym}</code> / ?\n"
                f"?? <b>??:</b> <i>{desc}</i>\n"
                f"?? <b>????:</b> <code>{available_qty}</code> ?\n\n"
                f"?? <b>???????????</b>"
            )
        case Language.HI:
            return (
                f"?? <b>??????:</b> <code>{cat_name}</code>\n"
                f"?? <b>????:</b> <code>{subcat_name}</code>\n"
                f"?? <b>?????:</b> <code>{unit_price:.2f} {sym}</code> / ????\n"
                f"?? <b>?????:</b> <i>{desc}</i>\n"
                f"?? <b>????? ???:</b> <code>{available_qty}</code> ???\n\n"
                f"?? <b>?????? ?? ??? ?????? ?????:</b>"
            )
        case Language.FR:
            return (
                f"?? <b>Cat?gorie:</b> <code>{cat_name}</code>\n"
                f"?? <b>Compte:</b> <code>{subcat_name}</code>\n"
                f"?? <b>Prix:</b> <code>{unit_price:.2f} {sym}</code> / compte\n"
                f"?? <b>Description:</b> <i>{desc}</i>\n"
                f"?? <b>En stock:</b> <code>{available_qty}</code> pcs\n\n"
                f"?? <b>S?lectionnez la quantit? ? acheter:</b>"
            )
        case Language.DE:
            return (
                f"?? <b>Kategorie:</b> <code>{cat_name}</code>\n"
                f"?? <b>Konto:</b> <code>{subcat_name}</code>\n"
                f"?? <b>Preis:</b> <code>{unit_price:.2f} {sym}</code> / Konto\n"
                f"?? <b>Beschreibung:</b> <i>{desc}</i>\n"
                f"?? <b>Vorr?tig:</b> <code>{available_qty}</code> Stk\n\n"
                f"?? <b>Menge ausw?hlen:</b>"
            )
        case Language.IT:
            return (
                f"?? <b>Categoria:</b> <code>{cat_name}</code>\n"
                f"?? <b>Account:</b> <code>{subcat_name}</code>\n"
                f"?? <b>Prezzo:</b> <code>{unit_price:.2f} {sym}</code> / acc\n"
                f"?? <b>Descrizione:</b> <i>{desc}</i>\n"
                f"?? <b>Disponibili:</b> <code>{available_qty}</code> pz\n\n"
                f"?? <b>Seleziona la quantit? da acquistare:</b>"
            )
        case Language.ES:
            return (
                f"?? <b>Categor?a:</b> <code>{cat_name}</code>\n"
                f"?? <b>Cuenta:</b> <code>{subcat_name}</code>\n"
                f"?? <b>Precio:</b> <code>{unit_price:.2f} {sym}</code> / cuenta\n"
                f"?? <b>Descripci?n:</b> <i>{desc}</i>\n"
                f"?? <b>En stock:</b> <code>{available_qty}</code> uds\n\n"
                f"?? <b>Selecciona la cantidad a comprar:</b>"
            )
        case _:
            return (
                f"?? <b>Category:</b> <code>{cat_name}</code>\n"
                f"?? <b>Account:</b> <code>{subcat_name}</code>\n"
                f"?? <b>Price:</b> <code>{unit_price:.2f} {sym}</code> / acc\n"
                f"?? <b>Description:</b> <i>{desc}</i>\n"
                f"?? <b>In stock:</b> <code>{available_qty}</code> pcs\n\n"
                f"?? <b>Select quantity to buy:</b>"
            )


def get_instant_buy_confirm_text(language: Language, cat_name: str, subcat_name: str, unit_price: float, qty: int, total_price: float, sym: str, balance: float, is_enough: bool, missing: float) -> tuple[str, dict]:
    match language:
        case Language.VI:
            status_text = (
                "? <b>S? d? v? ?? thanh to?n. B?m 'MUA NGAY' b?n d??i ?? nh?n t?i kho?n t?c th?!</b>"
                if is_enough
                else f"?? <b>S? d? v? kh?ng ??! C?n thi?u: <code>{missing:.2f} {sym}</code>. Vui l?ng n?p ti?n v?o v? tr??c khi mua.</b>"
            )
            msg = (
                "? <b>X?C NH?N MUA T?I KHO?N (TR? TI?N TR?C TI?P)</b>\n\n"
                f"?? <b>Danh m?c:</b> <code>{cat_name}</code>\n"
                f"?? <b>Lo?i t?i kho?n:</b> <code>{subcat_name}</code>\n"
                f"?? <b>??n gi?:</b> <code>{unit_price:.2f} {sym}</code> / nick\n"
                f"?? <b>S? l??ng mua:</b> <code>{qty}</code> nick\n"
                f"?? <b>T?NG THANH TO?N:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"?? <b>S? d? v? hi?n t?i:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "? <i>L?u ?: H? th?ng t? ??ng Check Live UID Facebook qua Graph API ngay khi giao h?ng, cam k?t 100% clone Live!</i>"
            )
            labels = {
                "buy": f"? MUA NGAY ({total_price:.2f} {sym})",
                "back_qty": "?? Ch?n l?i s? l??ng",
                "cancel": "? H?y b?",
                "binance": "?? N?p Binance Pay (0% Ph? - Nh?n ngay 1s)",
                "bank": "?? N?p Ng?n H?ng (VietQR / BIDV)",
                "crypto": "?? N?p On-chain Crypto"
            }
        case Language.ZH:
            status_text = (
                "? <b>????????????????????????</b>"
                if is_enough
                else f"?? <b>???????: <code>{missing:.2f} {sym}</code>?????????</b>"
            )
            msg = (
                "? <b>?????? (????)</b>\n\n"
                f"?? <b>??:</b> <code>{cat_name}</code>\n"
                f"?? <b>??:</b> <code>{subcat_name}</code>\n"
                f"?? <b>??:</b> <code>{unit_price:.2f} {sym}</code> / ?\n"
                f"?? <b>??:</b> <code>{qty}</code> ?\n"
                f"?? <b>???:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"?? <b>??????:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "? <i>??: ??????? Facebook Graph API ????? Live ????? 100% Live?</i>"
            )
            labels = {
                "buy": f"? ???? ({total_price:.2f} {sym})",
                "back_qty": "?? ??????",
                "cancel": "? ??",
                "binance": "?? ???? Binance Pay (0???)",
                "bank": "?? ???????? (VietQR)",
                "crypto": "?? ???? (On-chain)"
            }
        case _:
            status_text = (
                "? <b>Sufficient balance. Click 'BUY NOW' below to receive accounts immediately!</b>"
                if is_enough
                else f"?? <b>Insufficient balance! Missing: <code>{missing:.2f} {sym}</code>. Please top up your wallet.</b>"
            )
            msg = (
                "? <b>INSTANT PURCHASE CONFIRMATION</b>\n\n"
                f"?? <b>Category:</b> <code>{cat_name}</code>\n"
                f"?? <b>Account:</b> <code>{subcat_name}</code>\n"
                f"?? <b>Unit Price:</b> <code>{unit_price:.2f} {sym}</code> / acc\n"
                f"?? <b>Quantity:</b> <code>{qty}</code> pcs\n"
                f"?? <b>TOTAL AMOUNT:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"?? <b>Wallet Balance:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "? <i>Note: Live Facebook UIDs are automatically verified via Graph API upon delivery!</i>"
            )
            labels = {
                "buy": f"? BUY NOW ({total_price:.2f} {sym})",
                "back_qty": "?? Change quantity",
                "cancel": "? Cancel",
                "binance": "?? Deposit Binance Pay (0% Fee)",
                "bank": "?? Deposit Vietnam Bank (VietQR)",
                "crypto": "?? Deposit On-chain Crypto"
            }
    return msg, labels
