import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  TouchableOpacity, 
  ActivityIndicator, 
  Alert,
  ScrollView 
} from 'react-native';
import { doc, onSnapshot } from 'firebase/firestore';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { db } from '../services/firebaseConfig';
import { API_BASE_URL } from '../services/apiConfig';

export default function TimerScreen({ route, navigation }) {
  const { bookingId } = route.params;
  const [booking, setBooking] = useState(null);
  const [timeLeft, setTimeLeft] = useState('00:00:00');
  const [loading, setLoading] = useState(false);

  // 1. Listen for booking changes
  useEffect(() => {
    const docRef = doc(db, "bookings", bookingId.toString());
    const unsubscribe = onSnapshot(docRef, (docSnap) => {
      if (docSnap.exists()) {
        const data = docSnap.data();
        setBooking(data);
        
        // If state changes to otp_generated or retrieval approved, route to Retrieval screen
        if (data.booking_status === "otp_generated" || data.booking_status === "retrieval_approved") {
          navigation.navigate("Retrieval", { bookingId });
        }
        // If session is completed, go back home
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

  // 2. Set up countdown timer ticks
  useEffect(() => {
    if (!booking || !booking.start_time) return;

    const interval = setInterval(() => {
      const startTime = new Date(booking.start_time).getTime();
      const durationMs = booking.rental_duration * 60 * 1000;
      const endTime = startTime + durationMs;
      const remainingMs = Math.max(0, endTime - Date.now());

      if (remainingMs === 0) {
        setTimeLeft('00:00:00');
      } else {
        const hrs = Math.floor(remainingMs / 3600000);
        const mins = Math.floor((remainingMs % 3600000) / 60000);
        const secs = Math.floor((remainingMs % 60000) / 1000);
        
        const pad = (num) => String(num).padStart(2, '0');
        setTimeLeft(`${pad(hrs)}:${pad(mins)}:${pad(secs)}`);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [booking]);

  const handleRetrieveItems = async () => {
    setLoading(true);
    try {
      const token = await AsyncStorage.getItem('jwt_token');
      const response = await fetch(`${API_BASE_URL}/api/bookings/${bookingId}/generate-otp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "Failed to generate OTP");
      }

      // Success. Status transitions to otp_generated on the backend, 
      // which syncs to Firestore and routes the user to Retrieval screen automatically.
      Alert.alert("OTP Requested", "A 6-digit retrieval code has been generated and displayed on the physical locker's screen.");
    } catch (error) {
      console.error(error);
      Alert.alert("Error requesting retrieval", error.message);
    } finally {
      setLoading(false);
    }
  };

  if (!booking) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#ffffff" />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.card}>
        <Text style={styles.stateTitle}>Rental Active</Text>
        <Text style={styles.lockerText}>Locker ID: {booking.locker_id}</Text>

        <View style={styles.timerCircle}>
          <Text style={styles.timerLabel}>Time Remaining</Text>
          <Text style={styles.timerText}>{timeLeft}</Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Start Time:</Text>
          <Text style={styles.infoValue}>
            {booking.start_time ? new Date(booking.start_time).toLocaleTimeString() : 'N/A'}
          </Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Duration booked:</Text>
          <Text style={styles.infoValue}>{booking.rental_duration / 60} hour(s)</Text>
        </View>

        <TouchableOpacity 
          style={styles.retrieveButton}
          onPress={handleRetrieveItems}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#000000" />
          ) : (
            <Text style={styles.retrieveButtonText}>Retrieve Items 🔓</Text>
          )}
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    backgroundColor: '#000000',
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
    alignItems: 'center',
  },
  stateTitle: {
    color: '#22c55e',
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  lockerText: {
    color: '#ffffff',
    fontSize: 16,
    marginBottom: 24,
  },
  timerCircle: {
    width: 200,
    height: 200,
    borderRadius: 100,
    borderWidth: 3,
    borderColor: '#22c55e',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 32,
  },
  timerLabel: {
    color: '#a3a3a3',
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  timerText: {
    color: '#ffffff',
    fontSize: 32,
    fontWeight: 'bold',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    marginBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#262626',
    paddingBottom: 8,
  },
  infoLabel: {
    color: '#a3a3a3',
    fontSize: 15,
  },
  infoValue: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '600',
  },
  retrieveButton: {
    backgroundColor: '#ffffff',
    height: 52,
    width: '100%',
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 32,
  },
  retrieveButtonText: {
    color: '#000000',
    fontSize: 16,
    fontWeight: 'bold',
  }
});
