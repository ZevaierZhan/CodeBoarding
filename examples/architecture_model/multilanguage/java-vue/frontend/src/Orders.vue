<script setup lang="ts">
import { createOrder } from "./api";
async function submit() { await createOrder(); }
</script>
<template><button @click="submit">Create order</button></template>
