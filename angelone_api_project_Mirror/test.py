import inspect
import traceback

def search_scrip_debug(obj, search_terms=("NIFTY 50", "NIFTY")):
    """
    Robust caller for obj.searchScrip(...) which tries several calling conventions
    and inspects the function signature to use the correct parameter name.
    Returns the first matching scrip dict or None.
    """
    # Debug: show what attributes are available on the object
    print("Available SmartConnect methods (partial):")
    for name in ("searchScrip", "search_scrip", "searchScrips", "getInstrument", "get_instrument", "get_instruments"):
        if hasattr(obj, name):
            print(" -", name)

    # Get the actual attribute
    if not hasattr(obj, "searchScrip"):
        print("⚠️ Object has no attribute 'searchScrip'. Listing all methods for debugging:")
        print([n for n in dir(obj) if callable(getattr(obj, n)) and not n.startswith("_")][:50])
        return None

    func = getattr(obj, "searchScrip")
    print(f"\nsearchScrip object: {func}")
    try:
        sig = inspect.signature(func)
        print("Detected signature:", sig)
    except Exception as e:
        print("Could not get signature via inspect:", e)
        sig = None

    tried_calls = []

    # helper to attempt a call and capture results / exceptions
    def _try_call(callable_fn, *args, **kwargs):
        try:
            print(f"\nAttempting call: {callable_fn.__name__}(*{args}, **{kwargs})")
            res = callable_fn(*args, **kwargs)
            print("Call succeeded. Returned type:", type(res))
            return res
        except TypeError as te:
            print("TypeError:", te)
            tried_calls.append(("TypeError", args, kwargs, str(te)))
        except Exception as e:
            print("Exception:", e)
            traceback.print_exc()
            tried_calls.append(("Exception", args, kwargs, str(e)))
        return None

    # Try multiple ways to call based on typical SmartAPI wrappers
    likely_param_names = []
    if sig:
        # collect non-self parameters from signature
        for i, (pname, p) in enumerate(sig.parameters.items()):
            # skip 'self' or 'cls' if present
            if pname in ("self", "cls"):
                continue
            likely_param_names.append(pname)

    # Common names that wrappers sometimes use
    common_names = ["searchscrip", "searchScrip", "scrip", "keyword", "query", "symbol", "search_string"]

    # Merge lists while keeping unique order
    for name in common_names:
        if name not in likely_param_names:
            likely_param_names.append(name)

    # 1) Try positional call with single term
    for term in search_terms:
        print("\n--- trying search term:", term)
        res = _try_call(func, term)
        if res:
            return normalize_search_result(res)

        # 2) Try calling as keyword with detected param names
        for pname in likely_param_names:
            kwargs = {pname: term}
            res = _try_call(func, **kwargs)
            if res:
                return normalize_search_result(res)

        # 3) Try uppercase/lowercase variations
        res = _try_call(func, term.upper())
        if res:
            return normalize_search_result(res)
        res = _try_call(func, term.lower())
        if res:
            return normalize_search_result(res)

    # If we reach here no call returned results
    print("\nAll attempted calls failed. Summary of attempts:")
    for t in tried_calls:
        print(t)
    return None

def normalize_search_result(res):
    """
    Normalize typical SmartAPI search result forms to a list of dicts.
    """
    # If the result is a dict with keys like 'data' or 'result', drill in
    if isinstance(res, dict):
        # many SmartAPI responses wrap data in res['data'] or res.get('data', res.get('result'))
        for key in ("data", "result", "response"):
            if key in res and isinstance(res[key], (list, dict)):
                res = res[key]
                break

    # If it's a list, return first matching or the list
    if isinstance(res, list):
        if not res:
            return None
        # Try to find an item with 'NIFTY' in symbol/tradingSymbol/name
        for item in res:
            if not isinstance(item, dict):
                continue
            sym = (item.get("symbol") or item.get("tradingSymbol") or item.get("name") or "").upper()
            exch = (item.get("exchange") or "").upper()
            if "NIFTY" in sym and exch in ("NSE", "NFO", ""):
                print("Found candidate in results:", sym, item.get("token"))
                return item
        # fallback: return first item
        print("No exact NIFTY in list; returning first item.")
        return res[0]
    elif isinstance(res, dict):
        # single dict returned
        return res
    else:
        print("Returned unexpected type:", type(res))
        return None
