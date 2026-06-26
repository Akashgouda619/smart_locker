import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  TextInput, 
  TouchableOpacity, 
  ActivityIndicator, 
  Alert,
  Linking,
  ScrollView,
  KeyboardAvoidingView,
  Platform 
} from 'react-native';
import { doc, onSnapshot } from 'firebase/firestore';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { db } from '../services/firebaseConfig';
import { API_BASE_URL } from '../services/apiConfig';

export default function PaymentScreen({ route, navigation }) {
  const { bookingId } = route.params;
  const [booking, setBooking] = useState(null);
  const [utr, setUtr] = useState('');
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [closing, setClosing] = useState(false);

  // Real-time listener for this booking's state changes in Firestore
  useEffect(() => {
    const docRef = doc(db, "bookings", bookingId.toString());
    const unsubscribe = onSnapshot(docRef, (docSnap) => {
      if (docSnap.exists()) {
        const data = docSnap.data();
        setBooking(data);

        // If booking is cancelled or complete, return home
        if (data.booking_status === "cancelled" || data.booking_status === "completed") {
          navigation.navigate("Home");
        }
        // If state changes to active rental, go to Timer screen
        if (data.booking_status === "active_rental") {
          navigation.navigate("Timer", { bookingId });
        }
      } else {
        navigation.navigate("Home");
      }
    }, (error) => {
      console.error("Firestore booking snapshot error:", error);
    });

    return unsubscribe;
  }, [bookingId, navigation]);

  const handleUPIPayment = () => {
    if (!booking) return;

    const payeeVpa = "7019007474@ptaxis";
    const payeeName = "Akashgouda G Kopparad";
    const amount = booking.amount || 20;
    const note = `Locker Booking ID ${bookingId}`;

    // Standard UPI Intent URI scheme
    const upiUrl = `upi://pay?pa=${payeeVpa}&pn=${encodeURIComponent(payeeName)}&am=${amount}&cu=INR&tn=${encodeURIComponent(note)}`;

    Linking.canOpenURL(upiUrl)
      .then((supported) => {
        if (supported) {
          Linking.openURL(upiUrl);
        } else {
          Alert.alert(
            "UPI App Not Found", 
            "We couldn't detect any UPI payment apps (like GPay, PhonePe, or Paytm) installed. Alternatively, you can scan the QR code displayed on the physical locker screen."
          );
        }
      })
      .catch((err) => console.error("UPI link opening failed:", err));
  };

  const handleConfirmPayment = async () => {
    if (!utr || utr.length !== 12 || isNaN(utr)) {
      Alert.alert("Invalid UTR", "UTR must be a 12-digit numeric transaction reference number.");
      return;
    }

    setLoading(true);
    try {
      const token = await AsyncStorage.getItem('jwt_token');
      const response = await fetch(`${API_BASE_URL}/api/payment/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          booking_id: bookingId,
          utr_ref: utr
        })
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "UTR validation failed");
      }

      // Success alert. Backend will verify and shift booking state,
      // which will update Firestore and trigger our UI transition.
      Alert.alert("UTR Submitted", "Verifying payment. The door will unlock shortly.");
    } catch (error) {
      console.error(error);
      Alert.alert("Verification Error", error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCloseDoor = async () => {
    setClosing(true);
    try {
      const token = await AsyncStorage.getItem('jwt_token');
      const response = await fetch(`${API_BASE_URL}/api/bookings/${bookingId}/close-storage`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "Failed to close door");
      }

      // Lock closed. Route will change automatically via Firestore sync to Timer screen.
    } catch (error) {
      console.error(error);
      Alert.alert("Error", error.message);
    } finally {
      setClosing(false);
    }
  };

  const handleCancelBooking = async () => {
    Alert.alert(
      "Cancel Booking",
      "Are you sure you want to cancel this booking reservation?",
      [
        { text: "No", style: "cancel" },
        { 
          text: "Yes, Cancel", 
          onPress: async () => {
            setCancelling(true);
            try {
              const token = await AsyncStorage.getItem('jwt_token');
              const response = await fetch(`${API_BASE_URL}/api/bookings/cancel`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ booking_id: bookingId })
              });

              const data = await response.json();
              if (!data.success) {
                throw new Error(data.message || "Cancellation failed");
              }
              navigation.navigate("Home");
            } catch (error) {
              console.error(error);
              Alert.alert("Cancellation Error", error.message);
            } finally {
              setCancelling(false);
            }
          }
        }
      ]
    );
  };

  if (!booking) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#ffffff" />
      </View>
    );
  }

  const isPending = booking.booking_status === "pending_payment";
  const isWaitingClose = booking.booking_status === "waiting_for_door_close";

  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.title}>Locker Reservation</Text>
          <Text style={styles.label}>Locker Code: {booking.locker_id}</Text>
          <Text style={styles.label}>Booking ID: #{booking.booking_id}</Text>
          
          <View style={styles.divider} />

          {isPending && (
            <>
              <Text style={styles.instruction}>
                Scan the QR code displayed on the physical locker screen to pay, or click the button below to pay directly on this device.
              </Text>

              <TouchableOpacity style={styles.upiButton} onPress={handleUPIPayment}>
                <Text style={styles.upiButtonText}>Pay via UPI App (₹{booking.amount})</Text>
              </TouchableOpacity>

              <View style={styles.inputGroup}>
                <Text style={styles.fieldLabel}>Enter 12-Digit UPI Transaction UTR</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g. 123456789012"
                  placeholderTextColor="#a3a3a3"
                  keyboardType="numeric"
                  maxLength={12}
                  value={utr}
                  onChangeText={setUtr}
                />
              </View>

              <TouchableOpacity 
                style={styles.confirmButton}
                onPress={handleConfirmPayment}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#000000" />
                ) : (
                  <Text style={styles.confirmButtonText}>Confirm Payment</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.cancelButton}
                onPress={handleCancelBooking}
                disabled={cancelling}
              >
                {cancelling ? (
                  <ActivityIndicator color="#ef4444" />
                ) : (
                  <Text style={styles.cancelButtonText}>Cancel Reservation</Text>
                )}
              </TouchableOpacity>
            </>
          )}

          {isWaitingClose && (
            <View style={styles.unlockedContainer}>
              <Text style={styles.successText}>✓ Payment Confirmed!</Text>
              <Text style={styles.doorUnlockTitle}>Locker Door Unlocked</Text>
              <Text style={styles.instructionText}>
                The locker door has physically unlocked. Please place your items inside.
              </Text>
              <Text style={styles.instructionTextBold}>
                After placing your items, push the locker door shut and press the button below:
              </Text>

              <TouchableOpacity 
                style={styles.confirmButton}
                onPress={handleCloseDoor}
                disabled={closing}
              >
                {closing ? (
                  <ActivityIndicator color="#000000" />
                ) : (
                  <Text style={styles.confirmButtonText}>CLOSE DOOR</Text>
                )}
              </TouchableOpacity>
            </View>
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#040807',
  },
  scrollContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 16,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#040807',
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    backgroundColor: '#0a1412',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#132c25',
    padding: 24,
  },
  title: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#10b981',
    marginBottom: 16,
    textAlign: 'center',
  },
  label: {
    color: '#6ee7b7',
    fontSize: 16,
    marginBottom: 6,
    textAlign: 'center',
  },
  divider: {
    height: 1,
    backgroundColor: '#132c25',
    marginVertical: 16,
  },
  instruction: {
    color: '#e6f4f1',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
  },
  upiButton: {
    backgroundColor: '#10b981',
    height: 48,
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  upiButtonText: {
    color: '#040807',
    fontSize: 15,
    fontWeight: 'bold',
  },
  inputGroup: {
    marginBottom: 16,
  },
  fieldLabel: {
    color: '#e6f4f1',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#11231f',
    color: '#e6f4f1',
    borderWidth: 1,
    borderColor: '#1d3d36',
    height: 48,
    borderRadius: 4,
    paddingHorizontal: 16,
    fontSize: 16,
  },
  confirmButton: {
    backgroundColor: '#10b981',
    height: 48,
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 12,
  },
  confirmButtonText: {
    color: '#040807',
    fontSize: 16,
    fontWeight: 'bold',
  },
  cancelButton: {
    borderWidth: 1,
    borderColor: '#ef4444',
    height: 48,
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 16,
  },
  cancelButtonText: {
    color: '#ef4444',
    fontSize: 15,
    fontWeight: '600',
  },
  unlockedContainer: {
    alignItems: 'center',
  },
  successText: {
    color: '#10b981',
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  doorUnlockTitle: {
    color: '#e6f4f1',
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 16,
  },
  instructionText: {
    color: '#6ee7b7',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 16,
  },
  instructionTextBold: {
    color: '#e6f4f1',
    fontSize: 14,
    fontWeight: 'bold',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  }
});
