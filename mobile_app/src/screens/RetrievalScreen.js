import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  TextInput, 
  TouchableOpacity, 
  ActivityIndicator, 
  Alert,
  ScrollView,
  KeyboardAvoidingView,
  Platform 
} from 'react-native';
import { doc, onSnapshot } from 'firebase/firestore';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { db } from '../services/firebaseConfig';
import { API_BASE_URL } from '../services/apiConfig';

export default function RetrievalScreen({ route, navigation }) {
  const { bookingId } = route.params;
  const [booking, setBooking] = useState(null);
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [closing, setClosing] = useState(false);

  // Real-time synchronization with Firestore booking state
  useEffect(() => {
    const docRef = doc(db, "bookings", bookingId.toString());
    const unsubscribe = onSnapshot(docRef, (docSnap) => {
      if (docSnap.exists()) {
        const data = docSnap.data();
        setBooking(data);

        // If booking gets completed, return home
        if (data.booking_status === "completed") {
          navigation.navigate("Home");
        }
      } else {
        navigation.navigate("Home");
      }
    }, (error) => {
      console.error("Firestore booking snapshot error:", error);
    });

    return unsubscribe;
  }, [bookingId, navigation]);

  const handleVerifyOTP = async () => {
    if (!otp || otp.length !== 6 || isNaN(otp)) {
      Alert.alert("Invalid OTP", "Please enter the 6-digit numeric OTP code displayed on the locker screen.");
      return;
    }

    setLoading(true);
    try {
      const token = await AsyncStorage.getItem('jwt_token');
      const response = await fetch(`${API_BASE_URL}/api/bookings/${bookingId}/verify-otp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ otp })
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "OTP verification failed");
      }

      // Success! Backend updates status to retrieval_approved,
      // which syncs to Firestore and refreshes our screen state.
      Alert.alert("OTP Verified", "Locker unlocked successfully.");
    } catch (error) {
      console.error(error);
      Alert.alert("Verification Error", error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCloseLocker = async () => {
    setClosing(true);
    try {
      const token = await AsyncStorage.getItem('jwt_token');
      const response = await fetch(`${API_BASE_URL}/api/bookings/${bookingId}/close-retrieval`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "Failed to complete retrieval");
      }

      // Success. Backend updates booking status to completed.
      // Firestore sync updates, our snapshot runs, and routes the user Home.
      Alert.alert("Locker Completed", "Locker session finalized. Thank you!");
    } catch (error) {
      console.error(error);
      Alert.alert("Error completing rental", error.message);
    } finally {
      setClosing(false);
    }
  };

  if (!booking) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#ffffff" />
      </View>
    );
  }

  const isOtpState = booking.booking_status === "otp_generated";
  const isApprovedState = booking.booking_status === "retrieval_approved";

  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.title}>Locker Retrieval</Text>
          <Text style={styles.label}>Locker Code: {booking.locker_id}</Text>

          <View style={styles.divider} />

          {isOtpState && (
            <>
              <Text style={styles.instruction}>
                Read the 6-digit one-time passcode (OTP) displayed inside the white box on the physical locker screen, and enter it below:
              </Text>

              <View style={styles.inputGroup}>
                <Text style={styles.fieldLabel}>Enter 6-Digit OTP Code</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g. 583721"
                  placeholderTextColor="#a3a3a3"
                  keyboardType="numeric"
                  maxLength={6}
                  value={otp}
                  onChangeText={setOtp}
                />
              </View>

              <TouchableOpacity 
                style={styles.confirmButton}
                onPress={handleVerifyOTP}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#000000" />
                ) : (
                  <Text style={styles.confirmButtonText}>Verify & Unlock Locker</Text>
                )}
              </TouchableOpacity>
            </>
          )}

          {isApprovedState && (
            <View style={styles.unlockedContainer}>
              <Text style={styles.successText}>✓ OTP Verified!</Text>
              <Text style={styles.doorUnlockTitle}>Locker Door Unlocked</Text>
              
              <Text style={styles.instructionText}>
                The locker door has physically unlocked. Please collect all your stored belongings.
              </Text>
              <Text style={styles.instructionTextBold}>
                After empty-checking the locker, push the door shut and click the button below to finalize your rental:
              </Text>

              <TouchableOpacity 
                style={styles.confirmButton}
                onPress={handleCloseLocker}
                disabled={closing}
              >
                {closing ? (
                  <ActivityIndicator color="#000000" />
                ) : (
                  <Text style={styles.confirmButtonText}>CLOSE LOCKER</Text>
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
    backgroundColor: '#000000',
  },
  scrollContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 16,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#000000',
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    backgroundColor: '#0c0c0e',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#ffffff',
    padding: 24,
  },
  title: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#ffffff',
    marginBottom: 16,
    textAlign: 'center',
  },
  label: {
    color: '#a3a3a3',
    fontSize: 16,
    marginBottom: 6,
    textAlign: 'center',
  },
  divider: {
    height: 1,
    backgroundColor: '#262626',
    marginVertical: 16,
  },
  instruction: {
    color: '#a3a3a3',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
  },
  inputGroup: {
    marginBottom: 16,
  },
  fieldLabel: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#ffffff',
    color: '#000000',
    height: 48,
    borderRadius: 4,
    paddingHorizontal: 16,
    fontSize: 16,
  },
  confirmButton: {
    backgroundColor: '#ffffff',
    height: 48,
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 12,
  },
  confirmButtonText: {
    color: '#000000',
    fontSize: 16,
    fontWeight: 'bold',
  },
  unlockedContainer: {
    alignItems: 'center',
  },
  successText: {
    color: '#22c55e',
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  doorUnlockTitle: {
    color: '#ffffff',
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 16,
  },
  instructionText: {
    color: '#a3a3a3',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 16,
  },
  instructionTextBold: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: 'bold',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  }
});
