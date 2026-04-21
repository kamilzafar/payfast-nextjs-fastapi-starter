<html>

<head>
    <link rel="stylesheet" type="text/css" href="form.css">
    <!-- CSS Bootstrap -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>

<body>
    <h2 style="text-align: center;">PayFast Example Code For Redirection Payment Request</h2>

    <?php

    $merchant_id = '102';
    $secured_key = 'zWHjBp2AlttNu1sK';
    $basket_id = 'FLUX-' . generateRandomString(4); // Generate basket_id with 4 random characters (letters and numbers)
    $trans_amount = '5';
    $currency_code = 'PKR';


    /**
     * Function to generate a random string of letters and numbers start here
     */
    function generateRandomString($length = 4)
    {
        $characters = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'; // Only capital letters and numbers
        $charactersLength = strlen($characters);
        $randomString = '';
        for ($i = 0; $i < $length; $i++) {
            $randomString .= $characters[rand(0, $charactersLength - 1)];
        }
        return $randomString;
    }

    /**
     * Function to generate a random string of letters and numbers ends here
     */

    /** Access Token Function starts here 
     * Get access token with merchant id, secured key, basket id, transaction amount, currency code
     * 
     */
    $token = getAccessToken(
        $merchant_id,
        $secured_key,
        $basket_id,
        $trans_amount,
        $currency_code

    );
    function getAccessToken(
        $merchant_id,
        $secured_key,
        $basket_id,
        $trans_amount,
        $currency_code

    ) {
        $tokenApiUrl = 'https://ipguat.apps.net.pk/Ecommerce/api/Transaction/GetAccessToken';
        $urlPostParams = sprintf(
            'MERCHANT_ID=%s&SECURED_KEY=%s&BASKET_ID=%s&TXNAMT=%s&CURRENCY_CODE=%s',
            $merchant_id,
            $secured_key,
            $basket_id,
            $trans_amount,
            $currency_code
        );

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $tokenApiUrl);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $urlPostParams);
        curl_setopt($ch, CURLOPT_USERAGENT, 'CURL/PHP PayFast Example');
        $response = curl_exec($ch);
        curl_close($ch);
        $payload = json_decode($response);
        $token = isset($payload->ACCESS_TOKEN) ? $payload->ACCESS_TOKEN : '';
        return $token;
    }

    /** Access Token Function ends here 
     */


    /**
     * process response coming from PayFast
     * 
     */

    /** Validation Hash starts here */
    /** Validation Hash ends here */
    ?>


    <!-- For data integrity purpose, transaction amount and basket_id should be the same as the ones sent in token request -->
    <!-- Actual Payment Request -->

    <form class="form-inline" id='PayFast_payment_form' name='PayFast-payment-form' method='post'
        action="https://ipguat.apps.net.pk/Ecommerce/api/Transaction/PostTransaction">



        CURRENCY_CODE: <input type="TEXT" name="CURRENCY_CODE" value="<?php echo $currency_code; ?>" /><br /> <br>
        Merchant_ID: <input type="TEXT" name="MERCHANT_ID" value="<?php echo $merchant_id; ?>" /><br /> <br>
        MERCHANT_NAME: <input type="TEXT" name="MERCHANT_NAME" value="Payfast Merchant" /><br /> <br>
        TOKEN: <input type="TEXT" name="TOKEN" value="<?php echo $token; ?>" /><br /> <br>
        BASKET_ID: <input type="TEXT" name="BASKET_ID" value="<?php echo $basket_id; ?>" /><br /> <br>
        TXNAMT: <input type="TEXT" name="TXNAMT" value="<?php echo $trans_amount; ?>" /><br /> <br>
        ORDER_DATE: <input type="TEXT" name="ORDER_DATE" value="<?php echo date('Y-m-d H:i:s', time()); ?>" /><br /> <br>
        SUCCESS_URL: <input type="TEXT" name="SUCCESS_URL" value="http://localhost/redirection/success.php" /><br /> <br>
        FAILURE_URL: <input type="TEXT" name="FAILURE_URL" value="http://localhost/redirection/failure.php" /><br /> <br>
        CHECKOUT_URL: <input type="TEXT" name="CHECKOUT_URL" value="http://localhost/redirection/checkout.php" /><br /> <br>
        CUSTOMER_EMAIL_ADDRESS: <input type="TEXT" name="CUSTOMER_EMAIL_ADDRESS" value="someone234@gmai.com" /><br /> <br>
        CUSTOMER_MOBILE_NO: <input type="TEXT" name="CUSTOMER_MOBILE_NO" value="03000000090" /><br /> <br>
        SIGNATURE: <input type="TEXT" name="SIGNATURE" value="SOMERANDOM-STRING" /><br /> <br>
        VERSION: <input type="TEXT" name="VERSION" value="MERCHANTCART-0.1" /><br /> <br>
        Item Description: <input type="TEXT" name="TXNDESC" value="Item Purchased from Cart" /><br /> <br>
        Proccode: <input type="TEXT" name="PROCCODE" value="00" /><br /> <br>
        Transaction Type: <input type="TEXT" name="TRAN_TYPE" value='ECOMM_PURCHASE' /><br /> <br>
        Store ID/Terminal ID (optional): <input type="TEXT" name="STORE_ID" value='' /><br /> <br>
        Create Recurring Token:
        <SELECT name="RECURRING_TXN">
            <option value="">Do NOT Create Token</option>
            <option value="TRUE">YES, Create Token</option>
        </SELECT>
        <br /> <br>

        <!-- Hiden Values -->

        <INPUT TYPE="HIDDEN" NAME="MERCHANT_USERAGENT" value="Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0">
        <INPUT TYPE="HIDDEN" NAME="ITEMS[0][SKU]" value="SAMPLE-SKU-01">
        <INPUT TYPE="HIDDEN" NAME="ITEMS[0][NAME]" value="An Awesome Dress">
        <INPUT TYPE="HIDDEN" NAME="ITEMS[0][PRICE]" value="150">
        <INPUT TYPE="HIDDEN" NAME="ITEMS[0][QTY]" value="2">
        <INPUT TYPE="HIDDEN" NAME="ITEMS[1][SKU]" value="SAMPLE-SKU-02">
        <INPUT TYPE="HIDDEN" NAME="ITEMS[1][NAME]" value="Ice Cream">
        <INPUT TYPE="HIDDEN" NAME="ITEMS[1][PRICE]" value="45">
        <INPUT TYPE="HIDDEN" NAME="ITEMS[1][QTY]" value="5">

        <!-- Hiden Values -->

        <!-- <input type="SUBMIT" value="SUBMIT"> -->
        <div class="row">
            <div class="col-md-12" style="text-align: center;">
                <input type="submit" id="submitBtn" value="Submit">
            </div>
        </div>
    </form>

    <script src="form.js"></script>
    <!-- JS Bootstrap -->
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.min.js"></script>
</body>

</html>