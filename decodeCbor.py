import cbor

# Assuming you have the raw CBOR response as bytes
# For example, if you fetched the response using a CoAP client:
cbor_response = b'\xa5itimestamps\x782000-01-01 01:50:07ktemperature\xfb@I\x0f\x5c\x28\xf5\xc2jlightLevel\x19\x04\x00hbinLevel\xfb@Y\x1e\xb8Q\xeb\x85hhumidity\xfb@G\xae\x14z\xe1\x47'

# Decode the CBOR data
decoded_data = cbor.loads(cbor_response)

# Print the decoded data
print(decoded_data)