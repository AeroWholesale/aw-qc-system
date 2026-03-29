const socket = io();

socket.on("test_result", (data) => {
    console.log("Test result received:", data);
});
