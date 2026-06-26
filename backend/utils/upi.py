from config import Config

def generate_upi_link(booking_id, amount, payee_name=None, vpa=None):
    """
    Generates a standard UPI deep link for payment processing.
    Format: upi://pay?pa=VPA&pn=NAME&am=AMOUNT&cu=INR&tn=NOTE&tr=TXN_REF
    """
    vpa = vpa or Config.UPI_VPA
    payee_name = payee_name or Config.UPI_PAYEE_NAME
    
    # URL encode payee name
    encoded_name = payee_name.replace(" ", "%20")
    
    # Note and transaction reference
    note = f"Locker%20Rental%20{booking_id}"
    txn_ref = f"BOOKING{booking_id}"
    
    upi_link = (
        f"upi://pay?"
        f"pa={vpa}&"
        f"pn={encoded_name}&"
        f"am={amount:.2f}&"
        f"cu=INR&"
        f"tn={note}&"
        f"tr={txn_ref}"
    )
    return upi_link
